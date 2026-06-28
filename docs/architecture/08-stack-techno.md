# 08 — Stack technologique recommandée

> **Rôle** : reco de technologies pour ce module, **croisée avec le référentiel** du monorepo `carto_entreprises`
> et en lien avec le [`00-hub.md`](00-hub.md) (§6). L'`État` indiqué = statut
> dans le référentiel du module (`technologies.xlsx`, feuille `web-scraping`). **Rien n'est imposé : l'utilisateur arbitre.**
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
| **Moteur interne** (pilotage/distribution/**reprise**) | **Temporal** | ✅ tranché | Durable execution : file, retries, **idempotence + checkpoints/reprise natifs** (groupe H). Workers Python = **activités**. Réutilise Postgres. **Remplace Celery** (ADR module 0001). |
| Cache / sessions | **Valkey** | À suivre | Cache (validateurs ETag) + sessions partagées. **Plus broker** — Temporal a sa propre persistance. Fork BSD de Redis. |
| **Store objet** (artefacts) | **Ceph RGW** | ✅ Sélectionné | `raw/` — réponse brute, rendu, snapshot, fichier, échange HTTP |
| Base (config/méta/dédup) | **PostgreSQL** | ✅ Sélectionné | *en aval (via manifest raw)* — l'acquisition n'écrit pas Postgres directement |
| Manifest / format | **Parquet** + JSON Pydantic | ✅ Sélectionné | Métadonnées sur Ceph RGW |
| **Validation tech + contrats** | **Pydantic** (+Pandera) | ✅ Sélectionné | Contrats du fichier 01 ; validation **technique** seule |
| Détection (côté page) | **BotD** | À suivre | Observer nos signaux d'automatisation → **classifier** et s'adapter |
| Checkpoints / reprise | **Temporal (natif)** | tranché | Reprise **event-sourced** = l'état du workflow (groupe H « gratuit »). redb seulement si store local complémentaire. |
| Archivage WARC | **warcio** (+ArchiveBox) | À suivre | Sérialiser/rejouer l'échange HTTP |
| Observabilité *(couche 03, optionnelle)* | **OpenTelemetry** (instrumentation) + **VictoriaMetrics** (métriques/alertes) + **VictoriaLogs** (journaux) + **Tempo** (traces) + **Grafana** (dashboards) | À suivre | `correlation_id` bout-en-bout ; VictoriaMetrics **remplace** Prometheus/Mimir, VictoriaLogs **remplace** Loki (plus efficient RAM/disque, Apache-2.0) |
| Hygiène secrets | **Gitleaks** | ✅ Sélectionné | Anti-fuite (≠ coffre) |

### Détail par brique — rôle & réserve *(le « pourquoi » derrière la table)*

> La table ci-dessus est l'**aperçu** ; cette section donne le **détail** : à quoi sert chaque brique, ce
> qu'elle ne couvre PAS, et ses alternatives de repli. *Le module est un **projet autonome** (submodule
> `na-web-scraping`) ; son seul couplage au monorepo est le **contrat raw S3** — il n'écrit jamais Postgres/Qdrant/Neo4j.*

- **httpx — client HTTP de référence** *(✅ Sélectionné)*
  - *Rôle* : client HTTP **unique** de la couche — sync + async, HTTP/2, pool/keep-alive, timeouts granulaires,
    redirections contrôlées, **streaming** pour le téléchargement de fichiers et émission des **en-têtes
    conditionnels** (ETag / If-Modified-Since, détection 304). Couvre moteurs, session/réseau, réponse à classifier, cache.
  - *Réserve* : l'**impersonation TLS/JA3** (usurpation d'empreinte) n'est **pas** son rôle → `curl_cffi` au cran furtif (cf. §4). Repli haute-charge : **aiohttp** (concurrence pure-async) ; `requests` (sync simple).

- **niquests — transport HTTP/3 (QUIC)** *(À suivre)*
  - *Rôle* : repli quand un serveur **exige HTTP/3** ou une négociation moderne — successeur drop-in de `requests`, HTTP/2 **et** HTTP/3 natifs + async. Renseigne le champ `protocole` du contrat `HttpExchange`.
  - *Réserve* : négocie le protocole **honnête** ; pour l'impersonation, c'est `curl_cffi` (cascade). Repli bas-niveau : `urllib3.future`.

- **Playwright — rendu navigateur** *(✅ Sélectionné)*
  - *Rôle* : moteur navigateur **unique** (ADR 0009) — auto-wait, SPA, shadow-DOM ouvert, iframes, lazy-load,
    locators sémantiques (`get_by_role/text/label`), **contextes éphémères/jetables** (isolation fichier 07 §4),
    API réseau natives (request/response/route/HAR) pour capturer les sous-requêtes du rendu, et exécution du **mécanisme client** (défi JS/PoW, jeton CSRF, ré-auth).
  - *Réserve* : le **furtif** se greffe par-dessus (Patchright / Camoufox / nodriver, cf. §4). `pydoll` / `SeleniumBase` restent **À suivre** (pas Sélectionné). Shadow-DOM **fermé** non garanti (instrumentation CDP à valider, cf. §5).

- **Scrapy — crawl HTML déterministe** *(✅ Sélectionné)*
  - *Rôle* : socle du crawl (ADR 0009) — ordonnancement, **AutoThrottle** (rate-limiting), file d'URLs, parsing par `parsel`/`selectolax`. **Scrapy-Playwright** = pont propre pour escalader HTTP→navigateur **dans** le crawl.
  - *Réserve* : ne **pas** introduire Scrapy-Redis (peu utile). Le contrôleur de parcours priorisé (priorité/profondeur/budgets) déborde de Scrapy — **Frontera** (À suivre) ne se justifie que si la stratégie de visite l'exige ; sinon la file native suffit (cf. §5).

- **Dagster — plan de contrôle (externe)** *(✅ Sélectionné)*
  - *Rôle* : plan de contrôle **unique** côté monorepo (ADR 0013/0014/0015) — schedules, sensors, triggers, retries+backoff, backpressure, replanification gouvernée. **Pas de Beat Celery.**
  - *Réserve* : Dagster orchestre l'**exécution**, **pas** la décision — l'arbre de **politique** (respecter / ralentir / suspendre / arrêter) est de la logique métier à coder (cf. §5).

- **Temporal — moteur interne (pilotage / distribution / reprise)** *(✅ tranché — ADR module 0001)*
  - *Rôle* : **durable execution** — file, retries, **idempotence + checkpoints/reprise natifs** (groupe H, event-sourced). Workers Python = **activités**. Réutilise Postgres. **Remplace Celery.** Déclenché/capté par Dagster ; toute I/O en **activités** (déterminisme).
  - *Réserve* : service à opérer (serveur + DB), **assumé** (POC = base de production — le poids n'est pas un critère). Cantonné **intra-module** (Dagster déclenche, ADR 0013).

- **Valkey — cache / sessions** *(À suivre)*
  - *Rôle* : **cache** de version (clé URL → validateurs ETag/Last-Modified) + partage de **sessions/cookies** entre workers. Fork **BSD-3** de Redis, wire-compatible.
  - *Réserve* : **plus broker** — Temporal a sa propre persistance durable. Au POC single-node, un cookie-jar fichier ou Postgres suffit. Ne **pas** choisir Redis (refusé) ni Scrapy-Redis.

- **Ceph RGW — store objet des artefacts** *(✅ Sélectionné)*
  - *Rôle* : store objet **S3** cible (ADR 0007) — `raw/` (réponse brute, rendu, snapshot, fichier, échange HTTP) + tout le lac et les documents probants. Accès via **boto3** (cf. §5).
  - *Réserve* : ne **pas** choisir MinIO (édition communautaire archivée, ADR 0007). Repli plus léger : **SeaweedFS** (ou Garage). Versioning/lifecycle S3 à valider.

- **PostgreSQL — base relationnelle (config / méta / dédup)** *(✅ Sélectionné)*
  - *Rôle* : source de vérité ACID **en aval** — config des sources, index dédup (`hash`→`artifact_id`), observations d'acquisition (jamais dédupliquées), traçabilité ; JSONB pour le semi-structuré ; réutilisée par Temporal.
  - *Réserve* : **frontière de couche** — le module **ne se connecte PAS** à Postgres ; il écrit ses métadonnées dans le **manifest raw** (Ceph RGW), c'est `02_transform` qui persiste dans le schéma `audit`.

- **Parquet + JSON Pydantic — manifest / format** *(✅ Sélectionné)*
  - *Rôle* : format colonnaire cible (ADR 0007/0008) pour les métadonnées/manifests en lot sur Ceph RGW ; manifests unitaires en JSON sérialisé par Pydantic.
  - *Réserve* : aucune (Avro en réserve si échange ligne-à-ligne schématisé).

- **Pydantic (+Pandera) — validation technique + contrats** *(✅ Sélectionné)*
  - *Rôle* : contrat **unique** (ADR 0004) — modélise/valide les métadonnées **techniques** de l'artefact et de l'`HttpExchange` (status, content_type, size, encoding, hash, complétude), qualifie techniquement une page de refus/WAF vs réponse valide (**signaux techniques**, pas extraction de sens). **Pandera** pour les lots tabulaires + quarantaine déclarative.
  - *Réserve* : valide le **technique** ; l'extraction de **sens** vit plutôt en aval (cf. §3). Les garde-fous anti-zip-bomb / limites de stream sont du **code applicatif**, pas Pydantic (cf. §5).

- **BotD — détection côté page** *(À suivre)*
  - *Rôle* : lib JS **retournée contre nous-mêmes** — exécutée dans la page rendue pour **observer** quels signaux d'automatisation un site pourrait lire et **classifier** la protection (groupe F). MIT.
  - *Réserve* : heuristiques **côté client** à corréler avec les signaux serveur. Sert à **qualifier** la protection pour adapter la stratégie, pas à la contourner.

- **warcio (+ArchiveBox) — archivage WARC** *(À suivre)*
  - *Rôle* : lib Apache de lecture/écriture **WARC** — sérialiser l'échange HTTP brut en `.warc.gz` et le **rejouer** pour les tests de non-régression (fichier 07 §7). ArchiveBox pour l'archivage probant multi-format (HTML/PDF/PNG/WARC + index).
  - *Réserve* : warcio écrit du **WARC**, **pas** le modèle `HttpExchange` du blueprint → le **mapping WARC→`HttpExchange`** + dépôt raw/ reste à coder (cf. §5).

- **OpenTelemetry + VictoriaMetrics + VictoriaLogs + Tempo + Grafana — observabilité** *(À suivre, couche 03 optionnelle)*
  - *Rôle* : **OpenTelemetry** = pierre angulaire du `correlation_id` de bout en bout (fichier 07 §5), standard traces/métriques/logs (Apache-2.0). Stack de stockage/visualisation : **VictoriaMetrics** (métriques + alertes — taux de soft/hard block), **VictoriaLogs** (journaux des qualifications), **Tempo** (traces), **Grafana** (dashboards).
  - *Réserve* : **VictoriaMetrics remplace Prometheus/Mimir** et **VictoriaLogs remplace Loki** — plus **efficient** (RAM/disque), **Apache-2.0** (vs Loki/Mimir **AGPL**), **mature**, **ops simple** (binaires autonomes). Journaux à cardinalité maîtrisée ; le **masquage runtime** des secrets/PII n'est **pas** outillé (pré-prod, cf. §5).

- **Gitleaks — hygiène secrets** *(✅ Sélectionné)*
  - *Rôle* : seul secret-scanning **retenu** (MIT) — empêche la fuite de secrets en pre-commit/CI.
  - *Réserve* : **détecte** les fuites, ne **gère/stocke** pas les secrets — ce n'est **pas un coffre** (coffre = pré-prod, cf. §5).

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

### Cascade de repli par couche (ordre = **coût croissant** ; escalade **si bloqué / incomplet**)

| Couche | N1 — premier essai (le moins cher) | Replis N2 → N3 | Dernier recours |
|---|---|---|---|
| Transport HTTP | **httpx** | **curl_cffi** (TLS/JA3 — *furtif dès le transport*) · niquests (HTTP/3) · primp / rnet / tls-client | — |
| Crawl HTTP | **Scrapy** | Scrapy-Playwright (pont vers JS) · crawlee | — |
| Navigateur (si JS) | **Playwright** | — | furtif ↓ |
| **Furtif navigateur** | **Patchright** (Playwright-natif, CDP) | Camoufox (Firefox, fingerprint max) · nodriver (Cloudflare) | managé ↓ |
| Managé (externalise IP+TLS+nav.+challenges) | — | Zyte · Scrapfly · Bright Data · Oxylabs *(SaaS, hors socle)* | DLQ / revue |
| CAPTCHA | solveurs locaux (ddddocr, hcaptcha-challenger) | services (CapSolver, 2Captcha) *(SaaS)* | — |
| Parsing (structure, pour naviguer) | **parsel** · **selectolax** | lxml · BeautifulSoup | — |
| Extraction de contenu *(aval)* | **Trafilatura** | newspaper4k (news) · readability | IA : crawl4ai |
| Archivage WARC | **warcio** | — | ArchiveBox (app) |

**Pourquoi « coût croissant » et pas « le plus furtif d'abord » ?** Un navigateur furtif est **lent et lourd**
(Camoufox ~42 s/page) : le lancer sur **chaque** page — alors que la plupart ne sont pas protégées — exploserait le
**coût par enregistrement valide** (le vrai KPI, §6 `strategie-anti-bot`). On **n'escalade que si nécessaire**. Trois nuances :

- Le **furtif n'est pas absent au départ** : `curl_cffi` (impersonation TLS/JA3) est un furtif **N2 *cheap***, **avant** tout navigateur.
- **Entrée adaptative par domaine** : pour un domaine **connu protégé** (Cloudflare / DataDome…), le **routeur de stratégie
  entre directement** au cran furtif (mémoire / policy par domaine) — il ne re-grimpe pas l'échelle à chaque requête.
  → « le plus furtif d'abord » est **vrai pour un domaine connu protégé** ; pour un domaine **inconnu**, on sonde **au moins cher**.
- Le saut est piloté par la **classification de réponse** (soft / hard block, groupe F). Détail outil-par-outil = colonne
  **« Rang / repli »** du référentiel (`technologies.xlsx`).

## 5. Lacunes — ce que le référentiel **ne couvre pas**

> Distinction nette : les briques **comblées** (une techno a été tranchée) vs les lacunes **réelles** (rien au
> référentiel → **à coder** ou **différé pré-prod**). On ne garde ouvert que ce qui l'est vraiment.

### ✅ Briques comblées (tranchées, ajoutées **À suivre** au référentiel — feuille `web-scraping`)

- **Empreinte / dédup** → **hashlib (SHA-256)**, stdlib, zéro dépendance *(alt blake3 si dédup haute vitesse)*.
- **Sniffing MIME** (type réel par magic numbers) → **filetype** *(alt puremagic)*.
- **Charset / encodage** → **charset-normalizer**.
- **Cache HTTP conditionnel** (politique de fraîcheur, store des validateurs) → **Hishel** (au-dessus de httpx ; store dans Valkey/Postgres).
- **Client S3** pour écrire dans Ceph RGW `raw/` → **boto3** (ADR 0007) *(alt aioboto3 async / OpenDAL)*.
- **File durable / reprise / DLQ** → **Temporal natif** (event-sourced, bail/retries/idempotence — groupe H) ; `redb` reste une **option locale complémentaire** seulement.

### ⚠️ Lacunes réelles — à coder (aucun outil dédié)

- **Mapping WARC→`HttpExchange`** : les outils WARC (warcio À suivre, warcprox/pywb En attente) écrivent du **WARC**, pas le modèle `HttpExchange` du blueprint (fichier 01). Le mapping + dépôt Ceph RGW `raw/` reste à coder.
- **Classification du block SUBI en sortie** (soft vs hard : refus persistant, IP bloquée, contenu incomplet, throttling vs lenteur) + niveau de confiance + cause alternative (fichier 05 §2/§3). **CrowdSec** détecte des attaquants **entrants** (défensif), pas les blocks que le collecteur **subit** → qualificateur à **coder** au-dessus des briques honnêtes (httpx/Playwright). *CrowdSec = hors périmètre, simple réserve.*
- **Moteur de POLITIQUE de réaction gouvernée** (respecter / ralentir / replanifier / suspendre / arrêter / escalader selon qualification, fichier 05 §4). Aucun outil (OPA/Cerbos En attente, conçus pour l'autorisation applicative). Dagster orchestre l'**exécution**, l'arbre de politique reste à coder.
- **Disjoncteur (circuit-breaker) par source + budget de tentatives + backoff+jitter** (garde-fous §7). Aucune lib de résilience au référentiel (pybreaker/tenacity absents) → code applicatif.
- **Garde-fous anti-zip-bomb / limites de stream / quarantaine** : limites taille compressée↔décompressée et durée max de réponse = code applicatif sur httpx. Aucun scanner de contenu malveillant (ClamAV absent) pour le téléchargement malveillant (fichier 07 §4).
- **Downloader résilient + SFTP** : aucun gestionnaire de téléchargement robuste (reprise sur coupure, multi-connexion, checksum intégré — aria2/wget absents) ni client **SFTP** (handler `downloaders` SFTP de CLAUDE.md non outillé). Couvert par défaut via httpx ou FilesPipeline Scrapy, sans brique résiliente.
- **Rate-limit / concurrence par source** : pas d'outil dédié (Scrapy AutoThrottle pour le crawl ; sinon sémaphores / Temporal — brique applicative). La coordination distribuée (leader-election/locks) est **portée par Temporal** si besoin ; etcd reste hors besoin.

### 🔒 Lacunes différées — **phase pré-production** (sécurité, hors POC)

- **Coffre à secrets** (résolution d'identifiants, re-résolution à la reprise, masquage des journaux) : tous **En attente** (OpenBao/Vault/Infisical/SOPS). Au POC : variables d'environnement / fichiers Compose. Gitleaks détecte mais ne stocke pas.
- **Anti-SSRF / contrôle d'egress / DNS pinné anti-rebinding** : aucun outil ne filtre les IP résolues (plages privées/loopback, métadonnées cloud `169.254.169.254`), allowlist domaines, revalidation après redirection. À traiter au-dessus du client HTTP le moment venu.
- **Masquage / anonymisation runtime des secrets & PII dans les journaux** : Presidio **En attente** ; aucun outil Sélectionné.
- **Sandbox OS-level du navigateur** (gVisor / Firejail / conteneur durci) : aucun outil au-delà des contextes éphémères Playwright. L'isolation repose sur Docker/Compose + profil éphémère ; durcissement à combler.

## 6. Points ouverts — **arbitrage utilisateur** (non tranchés ici)

1. **Extraction des données métier (le *sens*) : dans le module, ou en aval ?** — l'**analyse de page pour
   naviguer** est, elle, **dans le module** (cf. §3). Pour l'extraction du *sens* (Trafilatura, newspaper4k,
   Scrapling, crawl4ai) : au POC c'est **libre** ; reste à fixer où elle vit (module vs futur module *extraction*).
2. **Furtif navigateur — ordre de préférence à confirmer** : Patchright > Camoufox > nodriver (tous **À suivre**) ; à promouvoir si un domaine connu protégé l'exige (entrée adaptative, §4).

### ✅ Décisions actées (anciennes anomalies du garde-fou — résolues)

- **httpx → Sélectionné** (était « À suivre ») : c'est la brique HTTP la plus fondamentale ; aiohttp en alternative haute-charge.
- **Moteur interne → Temporal** (remplace **Celery**) : durable execution, file/retries/idempotence/**reprise groupe H** natifs. **Valkey** reste **cache/sessions** (plus broker — l'ancien « doublon broker/cache non tranché » est levé).
- **Briques tranchées** : hashlib, filetype, charset-normalizer, Hishel, boto3 (alts À suivre : blake3, puremagic). Comblent les anciennes lacunes hash/MIME/charset/cache HTTP/client S3.
- **CrowdSec → hors périmètre** (À suivre) : défensif/entrant, **pas** le classifieur de block **sortant** (à coder, §5).
- **Extraction (newspaper4k / Scrapling / pydoll / SeleniumBase) → À suivre**, pas « Sélectionné » dans **ce** module : l'extraction de sens relève d'un module **aval** distinct ; meilleur extracteur générique = **Trafilatura**.
- **WARC** (warcio À suivre) reste **partiel** : il n'écrit pas le contrat `HttpExchange` → mapping à coder (seule lacune WARC encore ouverte, §5).

> Détail besoin-par-besoin (alternatives par cluster de modules) : analyse multi-agents du 2026-06-28, hors-repo.
> La **« feuille comparatifs »** citée en ADR vit dans le **référentiel monorepo** (`technologies-referentiel.xlsx`),
> pas dans ce module ; côté module, les états + la colonne **« Rang / repli »** vivent dans `technologies.xlsx`.
