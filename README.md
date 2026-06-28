# web-scraping — plateforme d'acquisition de contenu web

Module **autonome** (submodule de `carto_entreprises`, monté en `modules/web-scraping/`). Repo : `na-web-scraping`.

## Rôle

Acquérir des **pages web** (HTTP statique, rendu navigateur) et les **fichiers liés**, et produire des
**artefacts bruts + métadonnées techniques + échanges HTTP** déposés dans **SeaweedFS** (`raw/`).

- **Acquisition** — l'extraction métier vit plutôt en aval (côté monorepo).
- **Couplage** au monorepo = **contrat raw uniquement** (convention de clé/manifest SeaweedFS). Aucun import du monorepo.

## Documentation

Blueprint complet : [`docs/00-hub.md`](docs/00-hub.md) — architecture macro (10 groupes de modules A–J),
contrats, MVP, diagramme de composants. Décision côté monorepo : **ADR 0021**.

## Structure

- `src/web_scraping/` — `contracts` · `pilotage`(A) · `orchestration`(B) · `session_reseau`(C) · `moteurs`(D) ·
  `navigation`(E) · `protections`(F) · `validation`(G) · `persistance`(H) · `securite`(I) · `exploitation`(J)
- `docs/` — blueprint (`00-hub.md` → `07-…`), `strategie-anti-bot.md` (réf. partielle), `audit-captcha/` (veille)
- `tests/`

> **État** : init / placeholders volontaires — le code se remplira ensuite.
