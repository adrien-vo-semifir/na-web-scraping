# 08 — Structure du projet (monorepo)

> **Rôle** : arborescence de référence et règles de dépendance. Monorepo polyglotte, orchestration Temporal isolée pour rester remplaçable.
> **Prérequis** : `00-hub.md`.
> **Décisions appliquées** : monorepo ; Workflows en Go ; Activities polyglottes (Go, Java, TS, Python) ; contrats Protobuf ; capacité à abandonner Temporal sans réécrire la logique métier.

---

## 1. Principe directeur : réversibilité de l'orchestrateur

L'arborescence matérialise une frontière : **la logique métier n'importe jamais le SDK Temporal**. Temporal n'exécute pas votre code « de l'intérieur » ; il l'**appelle** depuis une couche d'enveloppes fine et isolée. Le jour où l'orchestrateur change, on remplace cette couche sans toucher au reste.

Règle de dépendance, absolue :

```text
contracts/             ──→ (rien)
core/                  ──→ contracts/                      JAMAIS Temporal
platform/              ──→ contracts/                      JAMAIS Temporal
orchestration/temporal ──→ core/ + contracts/ + Temporal   ← SEUL point de couplage
```

Le sens des flèches protège la réversibilité : `orchestration/` dépend de `core/`, jamais l'inverse.

> **Test de réversibilité** : si l'on supprime `orchestration/`, alors `core/`, `contracts/` et `platform/` doivent toujours compiler. Si non, du couplage a fui et doit être corrigé.

---

## 2. Arborescence

```text
acquisition/
├── compose.yaml                     Stack locale complète : `docker compose up` (POC)
│
├── .github/
│   └── workflows/                   CI (seul emplacement lu par GitHub Actions)
│       ├── build-selective.yml      Build par chemin modifié
│       ├── contracts-gen.yml        Régénération Protobuf des 4 langages
│       └── deploy.yml               Déploiement par image
│
├── docker/                          Un sous-répertoire par image (un par Worker)
│   ├── <worker>/                    Dockerfile (+ .dockerignore) par Worker
│   │   ├── Dockerfile
│   │   └── .dockerignore
│   ├── …                            Autres Workers selon les moteurs et langages
│   ├── workflow-worker/             Worker Go exécutant les Workflows
│   │   └── Dockerfile
│   └── control-api/
│       └── Dockerfile
│
├── contracts/                       Source unique des contrats — ZÉRO dépendance Temporal
│   ├── proto/
│   │   ├── command.proto            AcquisitionCommand
│   │   ├── result.proto             AcquisitionResult
│   │   ├── artifact.proto           Artifact
│   │   └── http_exchange.proto      HttpExchange
│   └── gen/                         Types générés, ne pas éditer à la main
│       ├── go/
│       ├── ts/
│       ├── python/
│       └── java/
│
├── core/                            CŒUR MÉTIER — agnostique de Temporal
│   ├── <moteur>-fetcher-<langage>/  Un sous-dossier par moteur d'acquisition (voir note)
│   ├── …                            Autres moteurs selon les besoins
│   └── shared/                      Validation technique, anti-SSRF, capture HttpExchange
│
├── orchestration/                   COUCHE DE COORDINATION — rôle stable
│   ├── temporal/                    Implémentation concrète (remplaçable)
│   │   ├── workflows-go/            Workflows (Go) : orchestration déterministe
│   │   ├── activities/              Une enveloppe par moteur de core/, dans le langage du moteur
│   │   │   ├── <moteur>-activity-<langage>/
│   │   │   └── …
│   │   └── worker-bootstrap/        Un bootstrap par langage présent ; enregistrement des Task Queues
│   └── (futur) autre-orchestrateur/ Un second orchestrateur s'ajoute ici, sans toucher au reste
│
├── platform/                        INFRASTRUCTURE MÉTIER — agnostique de Temporal
│   ├── control-api/                 Entrée REST : réception des commandes
│   ├── storage/                     Écriture brut, métadonnées, HttpExchange
│   └── crawl-controller/            Contrôleur de parcours : frontière, profondeur, découverte
│
├── k8s/
│   ├── workers/                     Déploiements + autoscaling par Task Queue
│   └── infra/                       Services partagés (Temporal, base, stockage objet, cache)
│
└── docs/                            Blueprint 00 → 08
```

---

## 3. Rôle de chaque couche

Quatre couches, trois rôles distincts. La distinction tient au **rôle**, pas à la technologie.

| Couche | Rôle | Change quand… | Connaît Temporal ? |
| --- | --- | --- | --- |
| `core/` | **Acquérir une ressource** (les moteurs, le travail concret) | un site cible évolue, une protection apparaît, le rendu s'améliore | Non |
| `platform/` | **Faire fonctionner la plateforme autour** (entrée, stockage, parcours) | le contrat d'API, le stockage ou la politique de parcours change | Non |
| `orchestration/` | **Coordonner dans le temps** (qui s'exécute quand, retries, reprise) | l'orchestrateur change | Oui — exclusivement |
| `contracts/` | **Vocabulaire partagé** entre tous les langages | un contrat évolue | Non |

### 3.1 `core/` — les moteurs

Chaque sous-dossier est un moteur exposant une fonction simple « commande entrante → résultat », sans dépendance à l'orchestration. La structure est générique : on crée **un sous-dossier par moteur réellement nécessaire**, nommé selon le motif `<moteur>-fetcher-<langage>`.

| Élément | Convention | Référence blueprint |
| --- | --- | --- |
| `<moteur>-fetcher-<langage>/` | Un dossier par moteur ; expose `fetch/render/download(cmd) → result` ; langage choisi selon le moteur | fichier 04 (moteurs et navigation) |
| `shared/` | Validation technique, anti-SSRF, capture de l'échange HTTP, communs aux moteurs | fichiers 03 § 4, 06 § 3 |

> Les noms concrets de moteurs ne sont pas figés dans ce document de référence : ils dépendent des sources à acquérir et se décident à l'implémentation. Le motif `<moteur>-fetcher-<langage>` est la convention de nommage, pas une liste imposée.

`core/` est appelable à la fois par les Activities Temporal (en production) et directement par un script de test ou un runner maison (sans lancer la plateforme). C'est ce qui rend l'abandon de Temporal possible.

### 3.2 `platform/` — l'infrastructure métier

Services de support durables, indépendants de l'orchestrateur.

| Sous-dossier | Rôle | Référence blueprint |
| --- | --- | --- |
| `control-api/` | Point d'entrée REST des commandes d'acquisition | fichier 02 § 1, hub MVP |
| `storage/` | Écriture du contenu brut, des métadonnées, des HttpExchange | fichier 06 § 5 |
| `crawl-controller/` | Frontière priorisée, profondeur, domaines, découverte | fichier 02 § 6 |

### 3.3 `orchestration/` — la couche de coordination

`orchestration/` est le **rôle** (coordonner dans le temps), stable. `orchestration/temporal/` est l'**implémentation** concrète, remplaçable. Le nom de la technologie vit à l'étage où il est vrai — l'implémentation — jamais à l'étage de la frontière. Un second orchestrateur s'ajouterait en `orchestration/autre/` sans renommer ni casser l'existant.

Seul `orchestration/temporal/` importe le SDK Temporal. Vocabulaire Temporal (voir fichier 02) :

| Sous-dossier | Contenu | Notion Temporal |
| --- | --- | --- |
| `temporal/workflows-go/` | Code d'orchestration déterministe | Workflow |
| `temporal/activities/` | Une enveloppe par moteur de `core/`, dans le langage de ce moteur | Activity |
| `temporal/worker-bootstrap/` | Un bootstrap par langage présent ; chaque Worker poll sa ou ses Task Queues | Worker, Task Queue |

Deux règles structurantes, indépendantes des moteurs concrets :

- **Langage de l'enveloppe = langage du moteur.** Une enveloppe d'Activity appelle directement la fonction de `core/` (appel in-process, pas réseau) ; elle est donc écrite dans le même langage que le moteur qu'elle habille. Le Workflow reste en Go quel que soit le langage des Activities — le routage entre langages passe par la Task Queue, pas par un appel direct.
- **Un Worker par langage.** Un Worker Temporal est mono-langage. `worker-bootstrap/` contient donc un point de démarrage par langage présent ; le Worker Go porte les Workflows et les éventuelles Activities Go, les autres Workers portent les Activities de leur langage.

Les enveloppes d'`activities/` sont minces par conception : elles traduisent la commande, appellent la fonction de `core/`, remontent le résultat. Toute la logique d'acquisition est dans `core/`, jamais dans l'enveloppe. Les noms concrets d'Activities ne sont pas figés ici : ils découlent des moteurs de `core/`, eux-mêmes décidés à l'implémentation.

---

## 4. Pourquoi `core/` et `platform/` sont séparés

Les deux ignorent Temporal, mais on ne les fusionne pas : ils ont des cycles de vie différents. `core/` « bouge avec le web » (sites cibles, protections, rendu). `platform/` « bouge avec vos décisions produit » (contrat d'API, stockage, parcours). Les séparer permet de faire évoluer l'un sans risquer l'autre, et de tester un moteur de `core/` sans démarrer toute la plateforme.

---

## 5. Effet d'un abandon de Temporal

| Couche | Sort | Raison |
| --- | --- | --- |
| `core/` | Conservée telle quelle | N'a jamais importé Temporal |
| `platform/` | Conservée telle quelle | N'a jamais importé Temporal |
| `contracts/` | Conservée telle quelle | Protobuf, aucun type Temporal |
| `orchestration/` | Jetée et réécrite avec le nouvel orchestrateur | Seul point de couplage |

Trois couches sur quatre survivent. Seule l'enveloppe de coordination est à refaire.

---

## 6. Contexte de build

En monorepo, chaque image a besoin d'accéder à `core/` et `contracts/gen/`, qui sont en dehors de son sous-répertoire `docker/`. Le **contexte de build est donc la racine du repo**, le Dockerfile étant désigné par son chemin.

Ligne de commande :

```bash
docker build -f docker/<worker>/Dockerfile -t <worker> .
```

Le `.` final (racine) est le contexte ; `-f` pointe le Dockerfile dans son sous-répertoire. Cela autorise `COPY core/<moteur>-fetcher-<langage>/ ...` et `COPY contracts/gen/<langage>/ ...` dans le Dockerfile.

Équivalent dans `compose.yaml` (à la racine, donc contexte déjà correct) :

```yaml
services:
  <worker>:
    build:
      context: .
      dockerfile: docker/<worker>/Dockerfile
```

Un `.dockerignore` à la racine exclut du contexte ce qui ne doit pas entrer dans les images (autres langages, artefacts de build, `docs/`).

---

## 7. Industrialisation POC → production

La structure source ne change pas entre POC et production ; seul l'outillage évolue.

| Aspect | POC | Production |
| --- | --- | --- |
| Structure source | Monorepo | Monorepo (inchangé) |
| Build | Global ou manuel | Sélectif par chemin modifié (`.github/workflows/build-selective.yml`) |
| Images | `compose.yaml` racine | Une image par Worker, déployée indépendamment |
| Scaling | Manuel | Autoscaling par Task Queue (`k8s/workers/`) |
| Contrats | Génération Protobuf à la demande | Génération versionnée en CI (`contracts-gen.yml`) |
| Isolation Temporal | Convention | Lint CI bloquant tout import du SDK Temporal hors `orchestration/temporal/` |

> **Garde-fou de réversibilité en CI** : une règle de lint vérifie qu'aucun fichier hors `orchestration/temporal/` n'importe le SDK Temporal. Elle transforme le principe de la section 1 en contrainte automatiquement vérifiée, et reste valable quand un second orchestrateur est ajouté sous `orchestration/`.