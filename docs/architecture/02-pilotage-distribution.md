# 02 — Pilotage et distribution

> **Groupes** : A (pilotage et parcours), B (orchestration distribuée).
> **Prérequis** : `00-hub.md`, `01-contrats-modele-donnees.md`.
> **Contenu** : déclenchement, contrôleur de parcours, file de tâches, routage, tiers de workers, traitement par lots (tamis), cycle de vie, garanties de traitement, résilience.
>
> **Réalisation (cf. `08-stack-techno.md` + ADR module 0001)** : ce fichier décrit le *comportement attendu* du pilotage et de la distribution, indépendamment de l'outil. Concrètement, ces fonctions ne sont **pas à construire** : le **moteur interne est Temporal** (durable execution). File à baux, file différée, file des échecs (DLQ), accusé de traitement, idempotence, réconciliation et reprise (checkpoints) sont des **primitives natives, event-sourced** (groupe H « gratuit »). Les **workers** sont des **activités** Temporal en Python (toute I/O dans une activité = déterminisme). **Valkey** sert au **cache / sessions partagées** (plus broker). Le **déclenchement** vient du **plan de contrôle Dagster** (monorepo, ADR 0013) : pas de second ordonnanceur (ni Schedules Temporal, ni Beat).

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

Fonctions de distribution couvertes : planification, file, priorité, réservation temporaire (bail), accusé de traitement, contrôle de concurrence, backpressure, répartition par capacité, mise à l'échelle, arrêt propre, file des échecs, réconciliation des tâches abandonnées. **Toutes ces fonctions sont natives Temporal** (cf. encart d'en-tête) — bail = *task lease*, réconciliation = *heartbeat / timeout*, file des échecs = DLQ event-sourced ; rien n'est à recoder. La **planification** (déclenchement) est, elle, externe : c'est **Dagster** (ADR 0013), pas un ordonnanceur interne.

Le routage de l'étape `ROUTE` (Statique → HTTP, Dynamique → rendu, Fichier → téléchargement) répartit chaque tâche **par capacité de worker**, pas par rang de cascade (cf. § 3 et § 4).

---

## 3. Tiers de workers (capacité, non rang)

Les workers sont segmentés en **trois pools** par **coût et capacité**, dimensionnés pour la volumétrie. Le **tag d'un worker = sa capacité technique**, **jamais le rang dans la cascade** d'escalade : le routeur (§ 2) et le tamis (§ 4) y adressent des tâches selon le besoin, pas selon une position figée.

| Pool | Capacité | Niveaux servis | Profil de mise à l'échelle |
| --- | --- | --- | --- |
| `http` | léger : httpx (N1) + curl_cffi (N2) | statique | scale massif, concurrence haute |
| `browser` | Chromium (rendu) | N3 | borné, RAM élevée |
| `stealth` | furtif (N4) | N4 | le plus petit, **isolé** (egress / proxies résidentiels dédiés, compteur de coût) |

Les pools sont **scalés indépendamment**. L'isolation du pool `stealth` sert surtout à cloisonner l'**egress** et les **proxies dédiés** et à porter un **compteur de coût** distinct.

---

## 4. Traitement par lots (tamis)

Modèle de **débit** complémentaire de l'escalade **par-URL** : une **catégorie de sites** forme un **lot** (par ex. 500 ou 10 000 sites) traité **niveau par niveau**. Le lot entier passe d'abord au niveau **le moins coûteux** (passe « normale » : N1/N2, pool `http`) ; les **succès sortent**, les **échecs sont persistés** et constituent l'**entrée de la passe supérieure** (`browser`, puis `stealth`), passe après passe.

```mermaid
flowchart TB
    L0[Lot · catégorie de sites<br>≈ 10 000] --> P1[Passe N1/N2 · pool http]
    P1 -- succès --> OUT1([Sortis])
    P1 -- échecs persistés ≈ 2 000 --> P2[Passe N3 · pool browser]
    P2 -- succès --> OUT2([Sortis])
    P2 -- échecs persistés ≈ 500 --> P3[Passe N4 · pool stealth]
    P3 -- succès --> OUT3([Sortis])
    P3 -- résidu ≈ 50 --> DLQ([File des échecs])
```

**Funnel observable** (ex. 10 000 → 2 000 → 500 → 50). Avantages :

- **maximise** la part traitée au niveau *cheap* avant d'engager les niveaux chers ;
- **batche** les ressources coûteuses (le pool `stealth` n'est lancé qu'une fois une vraie **fournée** constituée) ;
- **révision et scheduling indépendants** par niveau ;
- les **listes d'échecs** de chaque passe sont des **artefacts persistés**.

**Réalisation Temporal** : un niveau = une **itération** de workflow ; le passage au niveau supérieur se fait par **`continue-as-new`** sur la **liste d'échecs** (le résidu qui rétrécit à chaque passe). La file, les baux et la DLQ restent natifs (encart d'en-tête).

### Coexistence avec l'escalade par-URL

Les deux régimes **coexistent** et adressent les mêmes tiers (§ 3) :

| Régime | Optimise | Mécanique |
| --- | --- | --- |
| **Escalade par-URL** | latence par site | un workflow grimpe la cascade jusqu'au succès |
| **Tamis par-lots** | débit · observabilité · batch des ressources chères | passes successives sur le résidu d'échecs |

> Une évaluation **Windmill** a servi à comparer l'approche (fan-out déclaratif + partition des échecs) ; le **moteur du module reste Temporal** (ADR module 0001).

---

## 5. Machine d'état du cycle de vie

État canonique d'une acquisition, aligné sur les `final_status` du fichier 01. Cette FSM se modélise **« as code »** dans **Temporal** (corps de workflow) avec des modèles **Pydantic** pour les états et transitions ; la file durable qui la porte (bail, DLQ, réconciliation) est **native Temporal**, pas un composant à construire.

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

## 6. Idempotence et garanties

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

## 7. Diagramme de séquence — réservation, exécution, accusé

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

Le bail (réservation temporaire) protège contre la perte d'un worker : si l'accusé n'arrive pas avant l'expiration, le réconciliateur ré-enfile la tâche. Couplé à l'idempotence (§ 6), cela donne une sémantique « au moins une fois » sans double effet. **En pratique, Temporal fournit ce schéma nativement** : le bail et la réconciliation correspondent au *heartbeat* d'activité et au *timeout*, la ré-exécution étant rejouée depuis l'historique event-sourced.

---

## 8. Contrôleur de parcours

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

## 9. Résilience

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
