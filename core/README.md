# core/ — cœur métier (agnostique de Temporal)

Chaque sous-dossier est un **moteur** exposant `fetch / render / download(cmd) → result`, **sans** dépendance à
l'orchestration. Convention de nommage : **`<moteur>-fetcher-<langage>/`** (langage choisi selon le moteur).

| Élément | Rôle |
|---|---|
| `<moteur>-fetcher-<langage>/` | un moteur d'acquisition (ex. `http-fetcher-python/`, `browser-fetcher-ts/`) |
| `shared/` | validation technique, anti-SSRF, capture `HttpExchange` — communs aux moteurs |

> Les moteurs concrets se décident à l'implémentation (selon les sources). Le motif `<moteur>-fetcher-<langage>`
> est la convention, pas une liste imposée (cf. [`../docs/structure-projet.md`](../docs/structure-projet.md) §3.1).

`core/` est appelable **directement** (script/runner de test) **et** par les Activities Temporal — c'est ce qui
rend l'abandon de Temporal possible. **N'importe JAMAIS le SDK Temporal.**
