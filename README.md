# web-scraping — plateforme d'acquisition de contenu web

Module **autonome** (submodule de `carto_entreprises`, monté en `modules/web-scraping/`). Repo : `na-web-scraping`.

## Rôle

Acquérir des **pages web** (HTTP statique, rendu navigateur) et les **fichiers liés**, et produire des
**artefacts bruts + métadonnées techniques + échanges HTTP** déposés dans **Ceph RGW** (`raw/`).

- **Acquisition** — l'extraction métier vit plutôt en aval (côté monorepo).
- **Couplage** au monorepo = **contrat raw uniquement** (convention de clé/manifest Ceph RGW). Aucun import du monorepo.

## Documentation

Blueprint complet : [`docs/00-hub.md`](docs/00-hub.md) — architecture macro (10 groupes de modules A–J),
contrats, MVP, diagramme de composants. Décision côté monorepo : **ADR 0021**.

- Stack technologique : [`docs/08-stack-techno.md`](docs/08-stack-techno.md) — reco par domaine (moteur interne
  **Temporal**, store objet **Ceph RGW**, …), croisée avec le référentiel `docs/technologies.xlsx` (feuille `web-scraping`).

## Structure

- `src/web_scraping/` — `contracts` · `pilotage`(A) · `orchestration`(B) · `session_reseau`(C) · `moteurs`(D) ·
  `navigation`(E) · `protections`(F) · `validation`(G) · `persistance`(H) · `securite`(I) · `exploitation`(J)
- `docs/` — blueprint (`00-hub.md` → `08-stack-techno.md`) + `technologies.xlsx`, `strategie-anti-bot.md` (réf. partielle), `audit-captcha/` (veille)
- `tests/`

> **État** : init / placeholders volontaires — le code se remplira ensuite.
