# 06 — Validation et artefacts

> **Groupe** : G (validation et artefacts).
> **Prérequis** : `00-hub.md`, `01-contrats-modele-donnees.md`.
> **Contenu** : validation technique, cache et requêtes conditionnelles, déduplication avec observation, sorties.

---

## 1. Diagramme de composants

```plantuml
@startuml
skinparam componentStyle rectangle
skinparam shadowing false
skinparam defaultFontName "sans"

package "Aval acquisition (G)" {
  [Cache conditionnel] as CACHE
  [Validation technique] as VALID
  [Déduplication et observation] as DEDUP
  [Producteur de sorties] as OUT
}

database "Cache de version" as VCACHE
database "Stockage brut" as RAW
database "Métadonnées" as META
queue "Bus d'événements" as EVENT

[Moteurs] as ENGINE

ENGINE --> CACHE
CACHE --> VCACHE
ENGINE --> VALID
VALID --> DEDUP
DEDUP --> OUT
OUT --> RAW
OUT --> META
OUT --> EVENT
DEDUP ..> META : observation d'acquisition
@enduml
```

---

## 2. Cache et requêtes conditionnelles

Éviter de télécharger intégralement un contenu inchangé. Le cache de version conserve les informations fournies par la source (validateurs de version, dates).

```mermaid
flowchart LR
    RES[Ressource connue] --> CACHE{Métadonnées de version disponibles ?}
    CACHE -- Oui --> COND[Requête conditionnelle]
    CACHE -- Non --> FULL[Acquisition complète]
    COND --> MOD{Contenu modifié ?}
    MOD -- Non --> OBS[Observation sans nouvel artefact]
    MOD -- Oui --> FULL
    FULL --> STORE[Stocker le nouvel artefact]
```

Fonctions : conservation des informations de version, requête conditionnelle, détection de contenu non modifié, politique de fraîcheur, cache de métadonnées, expiration, invalidation. Un contenu inchangé produit l'état `UNCHANGED` (fichier 01 § 9) et une observation, pas un nouvel artefact.

---

## 3. Validation technique minimale

```mermaid
flowchart LR
    RESP[Réponse potentiellement valide] --> STATUS[Contrôle du statut]
    STATUS --> TYPE[Contrôle du type de contenu]
    TYPE --> SIZE[Contrôle de la taille]
    SIZE --> ENC[Détection de l'encodage]
    ENC --> COMP[Contrôle de complétude]
    COMP --> HASH[Calcul de l'empreinte]
    HASH --> DEDUP[Vers déduplication]
```

Cette validation reste technique : statut, type, taille, encodage, intégrité, présence du document, empreinte. Elle ne supprime pas le bruit, n'interprète pas le sens, ne produit pas le modèle métier (frontière hub § 4).

---

## 4. Déduplication et observation

> **Décision verrouillée (hub § 6).** Même si l'empreinte existe déjà, le contenu n'est pas purement ignoré : une **observation d'acquisition** est toujours enregistrée. La déduplication évite de dupliquer l'artefact physique, pas de tracer l'exécution.

```mermaid
flowchart LR
    HASH[Empreinte calculée] --> DUP{Artefact déjà présent ?}
    DUP -- Non --> STORE[Stocker le nouvel artefact]
    DUP -- Oui --> REUSE[Référencer l'artefact existant]
    STORE --> OBS[Créer une observation d'acquisition]
    REUSE --> OBS
    OBS --> EVENT[Publier le résultat]
```

Trois notions distinctes :

| Notion | Contenu | Dédupliquée ? |
| --- | --- | --- |
| Artefact | Contenu physique (`artifact_id`, immuable) | Oui — réutilisé si empreinte connue |
| Exécution enregistrée | Observation : date, statut, latence, fraîcheur, conformité | Non — toujours enregistrée |
| Notification de résultat | Événement `document.acquired` ou équivalent | Non — toujours émise |

L'observation apporte : preuve que la source a été interrogée, nouvelle date de vérification, statut HTTP courant, évolution de latence, résultat de conformité, mise à jour de fraîcheur.

---

## 5. Sorties de l'acquisition

```mermaid
flowchart TB
    DEDUP{Artefact déjà présent ?}
    DEDUP -- Non --> RAW[Réponse brute]
    DEDUP -- Non --> RENDERED[Document après exécution]
    DEDUP -- Non --> SNAP[Instantané de l'état de page]
    DEDUP -- Non --> DOWN[Fichier téléchargé]
    DEDUP -- Oui --> REF[Référence d'artefact existant]
    RAW --> EVENT[Notification de contenu disponible]
    RENDERED --> EVENT
    SNAP --> EVENT
    DOWN --> EVENT
    REF --> EVENT
    EXCH[Échange HTTP brut] --> RAWSTORE[Stockage brut pour analyse différée]
    META[Métadonnées techniques] --> METASTORE[Stockage des métadonnées]
    EVENT --> FEEDBACK[Vers boucle de retour]
```

Artefacts produits, définis de façon disjointe (fichier 01 § 5) : réponse brute, document après exécution, instantané de l'état de page, fichier téléchargé. L'échange HTTP brut (fichier 01 § 6) est archivé en parallèle pour analyse différée. Ces sorties alimentent la couche extraction, pas un traitement métier interne.
