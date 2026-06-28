# 08 — Stack technologique recommandée

> **Rôle** : reco de technologies pour ce module, **croisée avec le référentiel** du monorepo `carto_entreprises`
> et en lien avec le [`00-hub.md`](00-hub.md) (§6). L'`État` indiqué = statut
> dans le référentiel (`technologies-referentiel.xlsx`, monorepo). **Rien n'est imposé : l'utilisateur arbitre.**
> **Prérequis** : `00-hub.md`, `01-contrats-modele-donnees.md`.

## 1. Cadre

- Le module produit **artefacts bruts + métadonnées techniques + échanges HTTP**. *(L'extraction de sens vit
  plutôt en aval — note d'organisation, pas une contrainte au POC.)*
- **POC sans contrainte** : rotation d'identité/proxy, usurpation d'empreinte, furtivité, unlockers managés et
  solveurs CAPTCHA sont **disponibles**. Sécurité, légalité et RGPD → **phase pré-production** (pour plus tard).

## 2. Stack recommandée par domaine

| Domaine | Choix | État | Rôle |
|---|---|---|---|
| **Client HTTP** (cœur) | **httpx** | ✅ Sélectionné | Client unique : sync+async, HTTP/2, streaming (download), en-têtes conditionnels (ETag/304). Alt haute-charge : aiohttp |
| HTTP/3 | **niquests** | À suivre | Repli compat protocole moderne |
| **Rendu navigateur** | **Playwright** | ✅ Sélectionné | JS/SPA/shadow-DOM/iframes, contextes **éphémères**, capture réseau/HAR. Alt : SeleniumBase, pydoll |
| **Crawl HTML** | **Scrapy** | ✅ Sélectionné | Ordonnancement, AutoThrottle (respect), file d'URLs ; **Scrapy-Playwright** pour escalader vers le rendu JS |
| **Plan de contrôle** | **Dagster** | ✅ Sélectionné | Schedules/sensors/retries + replanification (côté monorepo, ADR 0013) |
| **Pool d'exécution** | **Celery** | ✅ Sélectionné | Workers (sans Beat) — *nécessite un broker* |
| Broker / cache | **Valkey** | À suivre → **tranché** | Broker Celery + session partagée + cache validateurs ; **fork BSD de Redis** (broker = Valkey, décision utilisateur) |
| **Store objet** (artefacts) | **SeaweedFS** | ✅ Sélectionné | `raw/` — réponse brute, rendu, snapshot, fichier, échange HTTP |
| Base (config/méta/dédup) | **PostgreSQL** | ✅ Sélectionné | *en aval (via manifest raw)* — l'acquisition n'écrit pas Postgres directement |
| Manifest / format | **Parquet** + JSON Pydantic | ✅ Sélectionné | Métadonnées sur SeaweedFS |
| **Validation tech + contrats** | **Pydantic** (+Pandera) | ✅ Sélectionné | Contrats du fichier 01 ; validation **technique** seule |
| Détection (côté page) | **BotD** | À suivre | Observer nos signaux d'automatisation → **classifier** et s'adapter |
| Checkpoints / reprise | **redb** | ✅ Sélectionné | KV embarqué (binding Python à valider) — ou Postgres |
| Archivage WARC | **warcio** (+ArchiveBox) | À suivre | Sérialiser/rejouer l'échange HTTP |
| Observabilité | **OpenTelemetry** +Prom/Grafana/Loki/Tempo | À suivre | `correlation_id` bout-en-bout |
| Hygiène secrets | **Gitleaks** | ✅ Sélectionné | Anti-fuite (≠ coffre) |

## 3. Analyser la page pour naviguer ≠ extraire le sens

**Analyser une page pour y naviguer** (trouver les liens, la pagination, le « suivant », décider la page
suivante, **recurser**) **fait partie du scraping** — c'est **dans le module** (groupe **A2** contrôleur de
parcours + groupe **E** navigation, **E6** « découverte par score »). Ce **n'est pas** de l'« extraction
métier ». À distinguer :

| Lire la **STRUCTURE** | Interpréter le **SENS** (plutôt en aval) |
|---|---|
| liens `<a href>`, pagination, position DOM, « suivant », frontière de crawl | fiche entreprise, CA, classement du sujet |
| **parsel · selectolax · lxml** + locators Playwright + **scoring de liens codé** | newspaper4k, Scrapling, crawl4ai, ScrapeGraphAI |

Une navigation « intelligente » qui s'appuie sur le **sens d'une page** (LLM) est possible. Deux options
(**décision utilisateur**) :
1. **Score déterministe** sur **métadonnées de lien** (texte d'ancre, URL, position) → dans le module (E6) ;
2. **Navigation assistée LLM** → soit un composant de scoring lisant les métadonnées de lien, soit
   renvoyée en aval (la couche extraction décide quoi re-crawler).

## 4. Cascade d'escalade anti-bot — disponible au POC

Cascade complète **disponible** au POC (sécurité / légalité / RGPD → phase pré-production). Ordre d'escalade
détaillé (HTTP → empreinte → navigateur → furtif → managé) dans [`strategie-anti-bot.md`](strategie-anti-bot.md) :

- **Furtif / anti-détection** — Camoufox, nodriver, Patchright, **playwright-stealth**, undetected-chromedriver,
  zendriver, botasaurus, CloakBrowser ; + **SeleniumBase « CDP Mode »** et **pydoll « humanize »**.
- **Impersonation TLS/JA3** — curl_cffi, primp, rnet, tls-client, utls. *Imiter l'empreinte d'un navigateur.*
- **Unlockers managés / solveurs CAPTCHA** — Bright Data, Scrapfly, ZenRows, 2Captcha, CapSolver, ddddocr,
  FlareSolverr, cloudscraper.
- **Extraction (plutôt en aval)** — Trafilatura, newspaper4k, crawl4ai, Firecrawl, ScrapeGraphAI,
  browser-use, Stagehand, Skyvern, Scrapling. *Note d'organisation (cf. §3), pas une contrainte.*

## 5. Lacunes — ce que le référentiel **ne couvre pas**

**À coder (aucun outil dédié)** : anti-SSRF / contrôle d'egress + DNS pinné *(phase pré-production)* · classification
du **block subi** (soft/hard, fichier 05) · **moteur de politique** de réaction · machine d'état + **file durable**
(bail/DLQ) · circuit-breaker/backoff · anti-zip-bomb/quarantaine · mapping **WARC→`HttpExchange`** (les outils WARC
n'écrivent pas le contrat du fichier 01).

**✅ Briques tranchées** (ajoutées **À suivre** au référentiel — feuille `web-scraping`) : empreinte/dédup
**hashlib (SHA-256)** *(alt blake3)* · sniffing MIME **filetype/puremagic** · charset **charset-normalizer** ·
cache HTTP conditionnel **Hishel** · client S3 **boto3** *(alt aioboto3 async / OpenDAL)* pour écrire dans SeaweedFS.

**Coffre à secrets** : Vault/OpenBao/SOPS sont **« En attente »**. La sécurité (dont le coffre et les checkpoints
sans secret en clair, fichier 07) relève de la **phase pré-production** (pour plus tard), pas du POC.

## 6. Points ouverts — **arbitrage utilisateur** (non tranchés ici)

1. **Promouvoir `httpx` « Sélectionné » ?** Aucun client HTTP n'est acté (tous « À suivre ») alors que c'est la
   brique la plus fondamentale du module.
2. **Extraction des données métier (le *sens*) : dans le module, ou en aval ?** — l'**analyse de page pour
   naviguer** est, elle, **dans le module** (cf. §3). Pour l'extraction du *sens* (newspaper4k / Scrapling /
   crawl4ai) : au POC c'est **libre** ; reste à fixer où elle vit (module vs futur module *extraction*).
3. ✅ **Broker tranché : Valkey** (broker Celery + cache + sessions ; fork BSD de Redis).
4. ✅ **Briques tranchées** (cf. §5) : hashlib/blake3, filetype/puremagic, charset-normalizer, Hishel, boto3.
5. ✅ **Client HTTP tranché : httpx « Sélectionné »** (sync+async, HTTP/2) ; aiohttp en alternative haute-charge.

> Détail besoin-par-besoin (alternatives par cluster de modules) : analyse multi-agents du 2026-06-28, hors-repo.
