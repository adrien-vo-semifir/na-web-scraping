# 04 — Moteur d'acquisition et navigation

> **Groupes** : D (moteurs), E (navigation).
> **Prérequis** : `00-hub.md`, `01-contrats-modele-donnees.md`, `03-session-reseau.md`.
> **Scope** : pages web. Trois moteurs — HTTP statique, rendu navigateur, téléchargement de fichier. Capture HTTP brute transverse.
> **Cœur fonctionnel** du blueprint : tout le détail de navigation est ici, pas masqué dans une boîte.

---

## 1. Diagramme de composants

```plantuml
@startuml
skinparam componentStyle rectangle
skinparam shadowing false
skinparam defaultFontName "sans"

package "Sélection (D)" {
  [Sélecteur de mode] as SEL
}

package "Moteurs (D)" {
  [Worker HTTP] as HTTP
  [Worker rendu navigateur] as BROWSER
  [Worker téléchargement] as FILE
  [Capture HTTP brute] as CAP
}

package "Navigation (E)" {
  [Détecteur d'état prêt] as READY
  [Diagnostic du timeout] as TIMEOUT
  [Gestionnaire de modes] as MODES
  [Navigation SPA] as SPA
  [Structures complexes] as COMPLEX
  [Découverte par score] as DISCOVER
  [Interaction formulaires] as FORM
}

[Couche réseau] as NET
[Validation aval] as VALID

SEL --> HTTP
SEL --> BROWSER
SEL --> FILE
HTTP --> NET
BROWSER --> NET
FILE --> NET
HTTP ..> CAP
BROWSER ..> CAP
CAP --> NET

BROWSER --> READY
READY --> TIMEOUT
READY --> MODES
MODES --> SPA
MODES --> COMPLEX
MODES --> DISCOVER
MODES --> FORM
SPA --> READY

HTTP --> VALID
BROWSER --> VALID
FILE --> VALID
CAP --> VALID
@enduml
```

La capture HTTP brute s'intercale sur le trajet réseau des moteurs HTTP et navigateur : chaque requête/réponse est archivée comme `HttpExchange` (fichier 01) avant traitement, pour analyse différée.

---

## 2. Sélection du mode — escalade de coût

Ne jamais lancer le rendu navigateur par défaut : il est nettement plus coûteux en mémoire, CPU et temps.

```mermaid
flowchart LR
    START[Commande] --> JS{JavaScript nécessaire ?}
    JS -- Non --> HTTP[Acquisition HTTP]
    JS -- Oui --> BROWSER[Rendu navigateur]
    HTTP --> VALID{Contenu attendu présent ?}
    VALID -- Oui --> OUT[Contenu brut]
    VALID -- Non --> ESCALATE[Escalade vers navigateur]
    ESCALATE --> BROWSER
    BROWSER --> OUT
    START -. fichier lié .-> FILE[Téléchargement de fichier]
    FILE --> OUT
```

| Mode | Déclencheur | Coût |
| --- | --- | --- |
| Acquisition HTTP | Contenu statique, pas d'exécution requise | Faible |
| Téléchargement de fichier | Ressource fichier référencée | Variable |
| Rendu navigateur | Contenu injecté par script, SPA | Élevé |

---

## 3. Capture HTTP brute pour analyse différée

Capacité transverse. Conserve l'intégralité de l'échange indépendamment du traitement du contenu.

```mermaid
flowchart LR
    REQ[Requête construite] --> RECORD_REQ[Enregistrer requête<br>méthode, url, en-têtes, corps]
    RECORD_REQ --> SEND[Émission via couche réseau]
    SEND --> RECORD_RESP[Enregistrer réponse<br>statut, en-têtes, corps brut]
    RECORD_RESP --> TIMINGS[Capturer timings et contexte réseau]
    TIMINGS --> STORE[Archiver l'échange HttpExchange]
    STORE --> CONTINUE[Poursuivre le traitement du contenu]
```

Pour le rendu navigateur, chaque requête réseau secondaire déclenchée par la page peut produire son propre `HttpExchange`, rattaché à la même `execution_id`. La politique de capture (document principal seul, ou toutes les requêtes) est un paramètre de la commande (`capture_http`).

---

## 4. Acquisition HTTP statique

```mermaid
flowchart LR
    BUILD[Construction de la requête] --> SEND[Envoi]
    SEND --> REDIR[Suivi contrôlé des redirections]
    REDIR --> RESP[Réponse directe]
    RESP --> PROTECT[Vers analyse des protections]
    RESP --> VALID[Vers validation technique]
```

Le suivi des redirections rejoue le contrôle anti-SSRF à chaque saut (fichier 03 § 4).

---

## 5. Rendu navigateur

```mermaid
flowchart LR
    INIT[Initialisation du contexte isolé] --> LOAD[Chargement initial]
    LOAD --> SCRIPT[Exécution des scripts de la page]
    SCRIPT --> LIVE[Construction du document vivant]
    LIVE --> EVENTS[Observation des événements et mutations]
    EVENTS --> READY[Vers détermination de l'état prêt]
    EVENTS --> PROTECT[Vers analyse des protections]
```

Le contexte navigateur est éphémère et cloisonné (fichier 07, isolation). L'acquisition porte sur le document après exécution, pas seulement sur le HTML initial.

---

## 6. Détermination de l'état prêt

Une SPA n'a pas toujours d'événement unique « chargement terminé ». La disponibilité se détermine par combinaison de conditions, jamais par simple attente temporelle ni par réseau inactif seul.

```mermaid
flowchart TB
    READINESS{Conditions de disponibilité}
    READINESS --> DOC[Document initial chargé]
    READINESS --> EXP[Élément ou état attendu]
    READINESS --> DOM[Structure stabilisée]
    READINESS --> NET[Activité réseau suffisamment stable]
    READINESS --> ROUTE[Route applicative stabilisée]
    READINESS --> DATA[Données applicatives disponibles]
    DOC --> READY[Page exploitable]
    EXP --> READY
    DOM --> READY
    NET --> READY
    ROUTE --> READY
    DATA --> READY
    READINESS --> TO[Délai dépassé]
    TO --> DIAG[Vers diagnostic du timeout]
    style READY fill:#1f5f3a,color:#fff
```

L'état « réseau totalement inactif » n'est pas utilisé seul : une SPA peut conserver des connexions permanentes ou émettre des appels périodiques.

---

## 7. Diagnostic du timeout

Un timeout n'est pas un échec terminal : c'est un symptôme à qualifier.

```mermaid
flowchart LR
    WAIT[Attente de disponibilité] --> TO{Délai dépassé ?}
    TO -- Non --> WAIT
    TO -- Oui --> DIAG[Diagnostic]
    DIAG --> SLOW[Chargement lent]
    DIAG --> BLOCK[Protection ou blocage]
    DIAG --> COND[Condition d'attente incorrecte]
    DIAG --> FAIL[Défaillance de la source]
    SLOW --> RETRY[Nouvelle tentative adaptée]
    BLOCK --> POLICY[Politique de réaction]
    COND --> ALT[Condition alternative]
    FAIL --> ERR[Échec]
```

Causes possibles : élément attendu absent, erreur JavaScript, ressource bloquée, route SPA non atteinte, contenu dans un cadre ou un Shadow DOM, flux réseau permanent, throttling, challenge ou page intermédiaire, sélecteur obsolète.

---

## 8. Modes de navigation

```mermaid
flowchart TB
    READY[Page exploitable] --> MODE{Mode de navigation}
    MODE --> GUIDED[Guidé par repère connu]
    MODE --> SEMANTIC[Par texte, rôle, libellé]
    MODE --> DISCOVERY[Sans sélecteur prédéfini]
    MODE --> SCENARIO[Par scénario et états]
    GUIDED --> LOCATE[Localisation de l'élément]
    SEMANTIC --> LOCATE
    DISCOVERY --> DISCOVER[Vers découverte par score]
    SCENARIO --> LOCATE
    LOCATE --> ACTION[Exécution d'une action]
    ACTION --> RESULT{Résultat}
    RESULT -- Nouvel état --> SPA[Vers navigation SPA]
    RESULT -- Nouvelle page --> LOAD[Vers chargement]
    RESULT -- Nouvel onglet --> COMPLEX[Vers structures complexes]
    RESULT -- Téléchargement --> FILE[Vers téléchargement]
    RESULT -- Échec --> RECOVER[Vers reprise / erreurs]
```

| Mode | Description | Exemple |
| --- | --- | --- |
| Guidé techniquement | Repère technique fourni | Cliquer sur un élément identifié |
| Guidé fonctionnellement | Texte, rôle, libellé, valeur | Cliquer sur « page suivante » |
| Découverte automatique | Analyse des actions disponibles | Parcourir les fiches d'un catalogue |
| Piloté par URL | Génération ou découverte d'adresses | Suivre une pagination numérotée |
| Piloté par état | Actions selon l'état courant | Authentification, recherche, détail |
| Hybride | Combinaison avec repli | Sélecteur principal et solutions de repli |

---

## 9. Navigation SPA

```mermaid
flowchart TB
    SPA[Changement d'état détecté] --> ROUTE[Changement de route]
    SPA --> MUT[Mutations du document]
    SPA --> ASYNC[Chargements asynchrones]
    SPA --> APP[État applicatif]
    ROUTE --> VALID[Validation du nouvel écran]
    MUT --> VALID
    ASYNC --> VALID
    APP --> VALID
    VALID --> MODE[Retour sélection du mode]
```

Attente correcte du nouvel écran — combinaison de conditions, comme en § 6 : route attendue atteinte, élément attendu présent, document suffisamment stable, données visibles, requêtes critiques terminées.

---

## 10. Structures de page complexes

```mermaid
flowchart TB
    LOCATE[Localisation] --> CONTEXT[Gestion des contextes]
    CONTEXT --> FRAME[Cadres intégrés]
    CONTEXT --> SHADOW{Shadow DOM ?}
    CONTEXT --> LAZY[Chargement différé]
    CONTEXT --> INFINITE[Défilement infini]
    CONTEXT --> VIRTUAL[Contenu virtualisé]
    CONTEXT --> MODAL[Fenêtres et modales]
    SHADOW -- Accessible --> OPEN[Parcours récursif]
    SHADOW -- Fermé --> CLOSED[Interface publique]
    FRAME --> ACTION[Action]
    OPEN --> ACTION
    CLOSED --> ACTION
    LAZY --> ACTION
    INFINITE --> ACTION
    VIRTUAL --> ACTION
    MODAL --> ACTION
```

| Structure | Stratégie |
| --- | --- |
| Shadow DOM ouvert | Parcours récursif des arbres accessibles |
| Shadow DOM fermé | Interaction par l'interface publique ou instrumentation autorisée |
| Cadres intégrés | Changement explicite de contexte |
| Chargement différé | Défilement ou interaction déclenchant le chargement |
| Défilement infini | Acquisition incrémentale jusqu'à condition d'arrêt |
| Contenu virtualisé | Capture progressive (les éléments précédents disparaissent) |
| Modales et fenêtres | Détection, changement de contexte, reprise du scénario |

---

## 11. Découverte sans sélecteur, pondérée par confiance

```mermaid
flowchart TB
    PAGE[État courant] --> DISC[Découverte des actions]
    DISC --> TEXT[Texte et libellé]
    DISC --> ROLE[Rôle fonctionnel]
    DISC --> ATTR[Attributs et relations]
    DISC --> POS[Position]
    DISC --> STRUCT[Similarité structurelle]
    DISC --> HIST[Historique]
    TEXT --> SCORE[Score de confiance]
    ROLE --> SCORE
    ATTR --> SCORE
    POS --> SCORE
    STRUCT --> SCORE
    HIST --> SCORE
    SCORE --> RANK[Classement]
    RANK --> TH{Confiance suffisante ?}
    TH -- Oui --> ACTION[Exécuter]
    TH -- Non --> REVIEW[Demander une règle ou suspendre]
```

| Critère | Utilité |
| --- | --- |
| Texte visible | Identifier « Suivant », « Détail », « Télécharger » |
| Rôle fonctionnel | Distinguer bouton, lien, champ, onglet |
| Adresse cible | Éviter les liens externes ou non pertinents |
| Position | Repérer navigation principale, pagination, pied de page |
| Similarité structurelle | Regrouper cartes ou lignes d'une liste |
| Historique | Éviter les boucles |
| État visible | Éviter éléments masqués ou désactivés |
| Résultat attendu | Vérifier qu'une action produit l'état recherché |

---

## 12. Interaction avec les formulaires

```mermaid
flowchart LR
    FORM[Détection du formulaire] --> FIELDS[Champs attendus]
    FIELDS --> ALLOWED[Champs autorisés par scénario / politique]
    ALLOWED --> FILL[Saisie des données]
    FILL --> CSRF[Association des jetons de session]
    CSRF --> SUBMIT[Soumission]
    SUBMIT --> SRVRESP[Capture technique de la réponse]
    SRVRESP --> PROTECT[Vers analyse des protections]
```

Vigilance honeypot : interagir **uniquement** avec les champs autorisés par le scénario, la politique de source ou une règle fonctionnelle validée — pas seulement les champs visibles, car un champ légitime peut être temporairement masqué et un piège peut paraître visible. La réponse de soumission est **capturée et classifiée techniquement** ; les erreurs fonctionnelles sont transmises à la couche d'extraction, non interprétées ici.

---

## 13. Diagramme d'état d'une session de navigation

Cycle de vie interne d'une session de rendu navigateur, du contexte à sa fermeture.

```mermaid
stateDiagram-v2
    [*] --> ContexteInitialise
    ContexteInitialise --> ChargementInitial
    ChargementInitial --> ExecutionScripts
    ExecutionScripts --> AttenteEtatPret
    AttenteEtatPret --> Exploitable : conditions réunies
    AttenteEtatPret --> Timeout : délai dépassé
    Timeout --> AttenteEtatPret : condition alternative
    Timeout --> Echec : non récupérable
    Exploitable --> Action
    Action --> AttenteEtatPret : nouvel état SPA
    Action --> Exploitable : action locale
    Action --> Capture : contenu disponible
    Capture --> Fermeture
    Echec --> Fermeture
    Fermeture --> [*]
```

---

## 14. Diagramme de séquence — escalade HTTP vers navigateur

```plantuml
@startuml
skinparam shadowing false
skinparam defaultFontName "sans"
participant "Sélecteur" as SEL
participant "Worker HTTP" as HTTP
participant "Capture brute" as CAP
participant "Worker rendu" as BROWSER
participant "Validation" as VALID

SEL -> HTTP : commande (strategy_hint=auto)
HTTP -> CAP : enregistrer l'échange
HTTP -> HTTP : analyser le contenu
alt contenu attendu présent
    HTTP -> VALID : contenu brut
else contenu insuffisant (rendu JS requis)
    HTTP --> SEL : escalade nécessaire
    SEL -> BROWSER : commande (strategy_hint=browser)
    BROWSER -> CAP : enregistrer les échanges
    BROWSER -> BROWSER : rendu + attente d'état prêt
    BROWSER -> VALID : document rendu
end
@enduml
```

L'échange HTTP initial est archivé même quand le contenu se révèle insuffisant : la capture brute sert l'analyse différée indépendamment du résultat fonctionnel.
