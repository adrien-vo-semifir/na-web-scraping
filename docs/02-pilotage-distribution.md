# 02 — Pilotage et distribution

> **Groupes** : A (pilotage et parcours), B (orchestration distribuée).
> **Prérequis** : `00-hub.md`, `01-contrats-modele-donnees.md`.
> **Contenu** : déclenchement, contrôleur de parcours, file de tâches, routage, cycle de vie, garanties de traitement, résilience.

---

## 1. Diagramme de composants

```plantuml
@startuml
skinparam componentStyle rectangle
skinparam shadowing false
skinparam defaultFontName "sans"

package "Pilotage (A)" {
  [Planificateur] as SCHED
  [API de contrôle] as API
  [Contrôleur de parcours] as CRAWL
  database "Configuration" as CFG
}

package "Distribution (B)" {
  [Producteur de tâches] as PROD
  [Gestion des priorités] as PRIO
  queue "File de tâches" as QUEUE
  queue "File différée" as DELAY
  queue "File des échecs" as DLQ
  [Routeur de workers] as ROUTER
  [Gestionnaire de cycle de vie] as LIFE
  [Réconciliateur] as RECON
}

[Moteurs] as ENGINE

SCHED --> PROD
API --> PROD
CRAWL --> PROD : AcquisitionCommand
CFG --> PROD
PROD --> PRIO
PRIO --> QUEUE
DELAY --> QUEUE
QUEUE --> ROUTER : réservation temporaire
ROUTER --> ENGINE
ENGINE --> LIFE : transitions d'état
LIFE --> DELAY : RETRYABLE
LIFE --> DLQ : PERMANENT
RECON --> QUEUE : tâches abandonnées
LIFE ..> RECON : baux expirés
ENGINE ..> CRAWL : observations et liens
@enduml
```

Le contrôleur de parcours et les moteurs sont séparés : le premier décide quoi visiter, les seconds exécutent. La boucle observations → parcours alimente la découverte sans fusionner les responsabilités.

---

## 2. Diagramme d'activité — du déclenchement à la terminaison

```mermaid
flowchart TB
    START([Déclenchement]) --> CTRL[Contrôle préalable]
    CTRL --> CHECK{Règles, quotas,<br>fréquence, concurrence}
    CHECK -- Refusé --> REJECT([Rejet])
    CHECK -- Accepté --> CMD[Construction de la commande]
    CMD --> CREATE[Création de la tâche]
    CREATE --> PRIO[Affectation de priorité]
    PRIO --> QUEUE[Mise en file]
    QUEUE --> LEASE[Réservation temporaire par un worker]
    LEASE --> ROUTE{Type de source}
    ROUTE -- Statique --> WHTTP[Worker HTTP]
    ROUTE -- Dynamique --> WBROW[Worker rendu]
    ROUTE -- Fichier --> WFILE[Worker téléchargement]
    WHTTP --> RESULT[Résultat technique]
    WBROW --> RESULT
    WFILE --> RESULT
    RESULT --> ACK{Traitement validé}
    ACK -- Oui --> DONE([Terminer])
    ACK -- Récupérable --> DELAY[File différée]
    ACK -- Définitif --> DEAD([File des échecs])
    DELAY --> QUEUE
```

Fonctions de distribution couvertes : planification, file, priorité, réservation temporaire (bail), accusé de traitement, contrôle de concurrence, backpressure, répartition par capacité, mise à l'échelle, arrêt propre, file des échecs, réconciliation des tâches abandonnées.

---

## 3. Machine d'état du cycle de vie

État canonique d'une acquisition, aligné sur les `final_status` du fichier 01.

```mermaid
stateDiagram-v2
    [*] --> Created
    Created --> Validated
    Created --> Rejected
    Validated --> Queued
    Queued --> Assigned
    Assigned --> Running
    Running --> Waiting
    Waiting --> Running
    Running --> Succeeded
    Running --> Unchanged
    Running --> RetryableFailure
    Running --> PermanentFailure
    Running --> Suspended
    Running --> Cancelled
    RetryableFailure --> Delayed
    Delayed --> Queued
    Suspended --> Queued : reprise autorisée
    Suspended --> Cancelled
    Succeeded --> Published
    Unchanged --> Published
    Published --> [*]
    Rejected --> [*]
    PermanentFailure --> [*]
    Cancelled --> [*]
```

### Attributs de transition

Chaque transition précise : acteur responsable, délai maximal, événement produit, possibilité de reprise, compteur de tentatives, motif de transition, conservation des artefacts intermédiaires.

| Transition | Acteur | Borne | Événement |
| --- | --- | --- | --- |
| `Created → Validated` | Contrôle préalable | — | `acquisition.validated` |
| `Assigned → Running` | Worker (bail acquis) | TTL de bail | `acquisition.started` |
| `Running → Waiting` | Worker (attente d'état prêt) | timeout | — |
| `Running → RetryableFailure` | Worker | — | `acquisition.retry` |
| `RetryableFailure → Delayed` | Cycle de vie | backoff | — |
| `Delayed → Queued` | Cycle de vie | délai écoulé | `acquisition.requeued` |
| `Running → Suspended` | Worker (checkpoint) | TTL checkpoint | `acquisition.suspended` |
| `Succeeded → Published` | Sorties | — | `document.acquired` |

---

## 4. Idempotence et garanties

```mermaid
flowchart LR
    CMD[Commande] --> KEY[Clé d'idempotence<br>acquisition_id + configuration_version]
    KEY --> SEEN{Exécution déjà aboutie ?}
    SEEN -- Oui --> REUSE[Réutiliser le résultat existant]
    SEEN -- Non --> RUN[Exécuter]
    RUN --> ATTEMPT[Incrément attempt_id]
    ATTEMPT --> PUBLISH[Publication réconciliable]
    REUSE --> PUBLISH
```

Principe : une nouvelle tentative réutilise `acquisition_id` et `execution_id`, n'incrémente que `attempt_id`, et ne crée jamais une nouvelle acquisition logique. La publication est réconciliable, de sorte qu'un événement émis deux fois ne produit pas de doublon en aval.

---

## 5. Diagramme de séquence — réservation, exécution, accusé

Dialogue entre file, worker et cycle de vie, avec gestion du bail.

```plantuml
@startuml
skinparam shadowing false
skinparam defaultFontName "sans"
actor "Déclencheur" as TRIG
participant "Producteur" as PROD
queue "File" as Q
participant "Worker" as W
participant "Cycle de vie" as LIFE
participant "Réconciliateur" as RECON

TRIG -> PROD : commande validée
PROD -> Q : enfiler (priorité)
W -> Q : réserver (bail TTL)
Q --> W : tâche + bail
W -> LIFE : Running
alt succès avant expiration du bail
    W -> LIFE : Succeeded
    LIFE -> Q : accusé, retrait
else échec récupérable
    W -> LIFE : RetryableFailure
    LIFE -> Q : ré-enfiler après backoff
else worker perdu (bail expiré)
    RECON -> LIFE : bail expiré détecté
    LIFE -> Q : ré-enfiler (réconciliation)
end
@enduml
```

Le bail (réservation temporaire) protège contre la perte d'un worker : si l'accusé n'arrive pas avant l'expiration, le réconciliateur ré-enfile la tâche. Couplé à l'idempotence (§ 4), cela donne une sémantique « au moins une fois » sans double effet.

---

## 6. Contrôleur de parcours

Découplé des moteurs. Gère la frontière priorisée et la boucle de découverte.

```mermaid
flowchart LR
    OBS[Observations et liens] --> SCORE[Évaluation de pertinence]
    SCORE --> URL[Correspondance d'adresse]
    SCORE --> DEPTH[Profondeur]
    SCORE --> DOMAIN[Domaine autorisé]
    SCORE --> FRESH[Fraîcheur]
    SCORE --> COST[Coût estimé]
    URL --> FRONTIER[Frontière priorisée]
    DEPTH --> FRONTIER
    DOMAIN --> FRONTIER
    FRESH --> FRONTIER
    COST --> FRONTIER
    FRONTIER --> NEXT[Prochaine ressource]
    NEXT --> VISITED{Déjà visitée ?}
    VISITED -- Non --> EMIT[Émettre une commande]
    VISITED -- Oui --> SKIP[Ignorer]
```

Responsabilités de la frontière : priorité, profondeur maximale, domaine autorisé, canonicalisation des adresses, détection des cycles, budget de pages, budget temporel, coût d'exécution estimé, fraîcheur attendue, reprise après erreur.

---

## 7. Résilience

```mermaid
flowchart TB
    ERR[Erreur observée] --> TYPE{Type d'erreur}
    TYPE -- Transitoire --> TRANS[Erreur temporaire]
    TYPE -- Permanente --> PERM[Erreur permanente]
    TRANS --> RETRY[Nouvelle tentative]
    RETRY --> BACKOFF[Temporisation progressive avec jitter]
    BACKOFF --> BREAKER[Disjoncteur par source]
    BREAKER --> LIMIT{Plafond de tentatives}
    LIMIT -- Restantes --> DELAY[File différée]
    LIMIT -- Atteint --> DLQ[File des échecs]
    PERM --> DLQ
```

> **Garde-fous obligatoires** : compteur de tentatives plafonné (`max_attempts`), disjoncteur par source pour suspendre une source défaillante, budget temporel par acquisition. Toute boucle de replanification est bornée — pas de réinjection infinie.
