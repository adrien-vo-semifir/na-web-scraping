# web-scraping — acquisition de contenu web (monorepo polyglotte)

Module **autonome** (submodule `na-web-scraping`). Acquiert des **pages web** (HTTP statique, rendu navigateur) et
les **fichiers liés**, et produit des **artefacts bruts + métadonnées + échanges HTTP** déposés dans un store S3
(**Ceph RGW** en prod), orchestrés par **Temporal** (Workflows **Go**, Activities **polyglottes**).

## Architecture — réversibilité de l'orchestrateur

La logique métier **n'importe jamais** le SDK Temporal ; Temporal est isolé dans `orchestration/temporal/`.
Détail : **[`docs/structure-projet.md`](docs/structure-projet.md)** (arborescence + règles de dépendance) et le
blueprint **[`docs/architecture/`](docs/architecture/00-hub.md)** (00 → 08).

| Couche | Rôle | Connaît Temporal ? |
|---|---|---|
| `contracts/` | vocabulaire partagé — Protobuf → `gen/{go,ts,python,java}` | non |
| `core/` | moteurs d'acquisition `<moteur>-fetcher-<langage>/` + `shared/` | non |
| `platform/` | `control-api` · `storage` · `crawl-controller` | non |
| `orchestration/temporal/` | `workflows-go` · `activities` · `worker-bootstrap` | **oui (seul)** |

> Test de réversibilité : supprimer `orchestration/` → `core/`, `platform/`, `contracts/` compilent toujours.
> Garde-fou CI : `.github/workflows/reversibility.yml`.

## Démarrage (POC)

```bash
docker compose up -d                    # infra : Temporal · Postgres · Valkey · S3 local (SeaweedFS)
cd contracts && buf generate            # contrats Protobuf → gen/ (4 langages)
docker compose --profile workers up -d  # + Workers (une fois le code prêt)
```

> **État** : squelette d'architecture posé (contrats + couches + docker/CI). Les moteurs `core/`, les enveloppes
> `activities/` et les workflows Go se remplissent ensuite, par moteur réellement nécessaire.
