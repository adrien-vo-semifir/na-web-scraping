# Reco stack — module web-scraping

## Stack recommandée (par domaine)

### Client HTTP de référence (acquisition statique, transport réseau, téléchargement de fichier, cache conditionnel)
- **Choix : httpx** _(À suivre)_
- Rôle : Client HTTP HONNÊTE unique de la couche : sync + async, HTTP/2, pool/keep-alive natif, timeouts granulaires, en-têtes standard cohérents, redirections contrôlées, streaming pour téléchargement de fichier et émission des en-têtes conditionnels (ETag/If-Modified-Since, détection 304). Couvre clusters Moteurs, Session/réseau, Détection (réponse à classifier) et Validation/cache. Alternatives de repli : aiohttp (concurrence pure-async), requests (sync simple).
- Réserve : AUCUN client HTTP n'est 'Sélectionné' au référentiel (httpx/aiohttp/requests/niquests tous 'À suivre') — à promouvoir. Compatibilité protocole (HTTP/2) ; impersonation/usurpation d'empreinte disponibles au POC via curl_cffi si besoin (cf. cascade).

### Transport HTTP/3 (QUIC) / compatibilité protocole moderne honnête
- **Choix : niquests** _(À suivre)_
- Rôle : Repli quand un serveur exige HTTP/3 ou une négociation de protocole moderne : successeur drop-in de requests, HTTP/2 ET HTTP/3 natifs + async. Renseigne le champ 'protocole' du contrat HttpExchange.
- Réserve : Négocie HTTP/2-3 standard. urllib3.future (En attente) = brique bas-niveau HTTP/3, repli plus profond. curl_cffi/curl-impersonate disponibles si l'impersonation TLS/JA3 est nécessaire (cf. cascade).

### Rendu navigateur / isolation / mécanisme client légitime (JS, SPA, shadow DOM, formulaires, profils éphémères, exécution d'un défi autorisé)
- **Choix : Playwright** _(Sélectionné)_
- Rôle : Moteur navigateur UNIQUE (ADR 0009) : auto-wait/état prêt, navigation SPA, shadow DOM ouvert, iframes, lazy-load/scroll infini, locators sémantiques (get_by_role/text/label), contextes éphémères/jetables (isolation fichier 07 §4), API réseau natives (request/response/route/HAR) pour la capture des sous-requêtes du rendu, et exécution du mécanisme client (défi JS/PoW, jeton CSRF, ré-auth). Alternatives Sélectionné : SeleniumBase, pydoll.
- Réserve : playwright-stealth/Patchright/rebrowser-playwright disponibles au POC pour le mode furtif (cf. cascade). SeleniumBase 'CDP Mode' et pydoll 'humanize=True' activables si besoin. Shadow DOM FERMÉ non garanti (instrumentation CDP à valider, voir lacunes).

### Crawl HTML déterministe / throttling respectueux / file d'URLs (socle workers HTTP)
- **Choix : Scrapy** _(Sélectionné)_
- Rôle : Socle du crawl HTML déterministe (ADR 0009) : ordonnancement des requêtes, AutoThrottle (rate-limiting), file d'URLs, parsing par parsel/selectolax. Scrapy-Playwright (À suivre) = glue propre pour escalader HTTP→navigateur DANS le crawl.
- Réserve : Single-node au POC. NE PAS introduire Scrapy-Redis (En attente, peu utile). L'extraction métier vit plutôt en aval (note neutre, non imposée).

### Plan de contrôle / déclenchement / scheduling / politique de réaction (replanifier, ralentir)
- **Choix : Dagster** _(Sélectionné)_
- Rôle : Plan de contrôle UNIQUE (ADR 0013/0014/0015) : schedules, sensors, triggers, contrôle préalable (règles/quotas/concurrence), retries avec backoff, backpressure. Porte la 'file différée' et la replanification gouvernée de la réaction aux soft blocks (fichier 05). Pas de Beat Celery.
- Réserve : L'arbre de décision de POLITIQUE (respecter/ralentir/suspendre/arrêter selon qualification) est de la logique métier à coder — Dagster orchestre l'EXÉCUTION, pas la décision (voir lacunes).

### Moteur de pilotage / distribution / reprise interne
- **Choix : Temporal** _(tranché — remplace Celery ; ADR module 0001, feuille `comparatifs`)_
- Rôle : durable execution : file, retries, **idempotence + checkpoints/reprise natifs** (groupe H). Workers Python = **activités**. Réutilise Postgres. Déclenché par Dagster (ADR 0013) ; toute I/O en activités (déterminisme).
- Réserve : service à opérer (serveur + DB), **assumé** (POC = base de production). Valkey reste **cache/sessions** (plus broker).

### Broker de file de tâches / cache / store de session partagé / cache de version (validateurs ETag)
- **Choix : Valkey** _(À suivre)_
- Rôle : Capacité broker+cache absente du socle, requise par Celery : transport de la file, partage de l'état de session/cookies entre workers, cache de version (clé=URL→validateurs ETag/Last-Modified). Fork Redis BSD-3 (licence propre), wire-compatible. Devient utile quand la distribution interne scale.
- Réserve : 'À suivre', pas verrouillé — choix à acter par l'utilisateur. Au POC single-node, un cookie-jar fichier ou PostgreSQL suffit. Broker simple : pas de garanties durables natives (bail/DLQ — voir lacunes). NE PAS choisir Redis (Refusé) ni Scrapy-Redis (En attente).

### Store objet des artefacts bruts (réponse brute, document rendu, snapshot, fichier, échanges HTTP) → raw/
- **Choix : Ceph RGW** _(Sélectionné)_
- Rôle : Store objet S3 cible verrouillé (ADR 0007, frontière CLAUDE.md : 01_ingest ne produit QUE du raw déposé en Ceph RGW). Porte tous les fichiers du lac (raw/staging/curated/...) et les documents probants. Repli plus léger : Garage (À suivre).
- Réserve : Versioning/lifecycle S3 à valider (ADR 0007). AUCUN client S3 Python concret n'est au référentiel (boto3/s3fs/minio-py absents) — seul OpenDAL (À suivre) approche ; un client S3 reste à acter (voir lacunes). NE PAS choisir MinIO (À suivre, AGPL gênant, édition communautaire archivée).

### Base relationnelle (config des sources, métadonnées, dédup par empreinte, observations, boucle de retour)
- **Choix : PostgreSQL** _(Sélectionné)_
- Rôle : Source de vérité ACID du socle en aval : config des sources, index dédup (hash→artifact_id + unicité), observations d'acquisition (toujours enregistrées, jamais dédupliquées — hub §6), traçabilité. JSONB pour le semi-structuré. Peut porter file/checkpoints façon Hatchet/DBOS sans broker externe.
- Réserve : FRONTIÈRE DE COUCHE : le module acquisition (01_ingest) ne se connecte PAS à Postgres — il écrit ses métadonnées dans le MANIFEST RAW (Ceph RGW) ; c'est 02_transform qui persiste dans le schéma audit. Postgres est donc la cible aval, pas l'écriture directe du collecteur.

### Sérialisation des métadonnées / manifest d'acquisition (format fichier sur Ceph RGW)
- **Choix : Apache Parquet** _(Sélectionné)_
- Rôle : Format colonnaire cible (ADR 0007/0008) pour les métadonnées/manifests en lot déposés sur Ceph RGW. Avro (À suivre) si échange ligne-à-ligne schématisé ; manifests unitaires JSON sérialisés par Pydantic.
- Réserve : Aucune.

### Validation technique minimale (statut/type/taille/encodage/intégrité/empreinte) + contrat de modèle
- **Choix : Pydantic** _(Sélectionné)_
- Rôle : Contrat unique (ADR 0004) : modélise et valide les métadonnées TECHNIQUES de l'artefact et de l'HttpExchange (status, content_type, size, encoding, hash, complétude), qualifie techniquement une page de refus/WAF vs réponse valide (signaux techniques, pas extraction de sens). Pandera (Sélectionné) pour la validation tabulaire de lots de métadonnées et la quarantaine déclarative.
- Réserve : Valide les métadonnées techniques ; l'extraction de sens vit plutôt en aval (note neutre). Les garde-fous anti-bombe-zip / limites de stream sont du code applicatif, pas Pydantic (voir lacunes).

### Détection/classification des protections côté navigateur (signaux d'automatisation, environnement) — pour QUALIFIER
- **Choix : BotD (fingerprintjs/BotD)** _(À suivre)_
- Rôle : Lib JS retournée contre nous-mêmes : exécutée dans la page rendue pour OBSERVER quels signaux d'automatisation un site pourrait lire et CLASSIFIER la protection (groupe F). FingerprintJS en alternative. MIT, single-node.
- Réserve : BotD 'Ralenti' (à surveiller). Heuristiques côté client à corréler avec les signaux serveur. Détecter pour QUALIFIER la protection et adapter la stratégie.

### Détection comportementale réseau (rate-limit/throttle/blocage) — moteur de parsing/scénarios réutilisable
- **Choix : CrowdSec** _(Sélectionné)_
- Rôle : Moteur de détection comportementale + réputation IP (MIT, Go, single-node). Son moteur de parsing/scénarios est réutilisable pour CLASSIFIER des patterns soft/hard block observés dans nos propres échanges/logs.
- Réserve : ANOMALIE D'USAGE : CrowdSec est conçu pour protéger NOTRE infra (attaquants ENTRANTS), pas pour qualifier les blocks que NOUS subissons en SORTIE. Réemploi à valider ; la classification du block sortant reste largement à coder (voir lacunes).

### Store de checkpoints / reprise (état sérialisable d'une navigation longue, sans secret en clair)
- **Choix : redb** _(Sélectionné)_
- Rôle : KV embarqué Rust ACID (format stabilisé v4.1) : store de checkpoints local single-node sans service séparé (étape, route, pagination, budget, dernière action validée). Ne stocke que des références — les secrets sont re-résolus au coffre à la reprise. Alternative naturelle : PostgreSQL (couplage métadonnées+checkpoints).
- Réserve : Lib Rust : binding Python à valider. fjall/RocksDB (À suivre) si volume d'écriture élevé.

### Archivage WARC de l'échange HTTP brut (req/resp) — matérialisation et replay sans rappeler la source
- **Choix : warcio** _(À suivre)_
- Rôle : Lib Apache de lecture/écriture WARC : brique la plus directe pour sérialiser l'échange HTTP brut en .warc.gz depuis les handlers d'acquisition, et le rejouer pour les tests de non-régression (fichier 07 §7) sans réécrire la cascade. ArchiveBox (Sélectionné, MIT) pour l'archivage probant multi-format (Kbis/statuts → HTML/PDF/PNG/WARC + index).
- Réserve : warcio écrit du WARC, PAS le modèle HttpExchange propre du blueprint : le mapping WARC→HttpExchange + dépôt Ceph RGW raw/ reste à coder (voir lacunes). warcprox/pywb (En attente, GPL) = réserve licence à valider avant produit.

### Observabilité (correlation_id de bout en bout, métriques par stratégie, traces, journaux, alertes)
- **Choix : OpenTelemetry** _(À suivre)_
- Rôle : Pierre angulaire du correlation_id de bout en bout (fichier 07 §5), standard traces/métriques/logs (Apache-2.0). Stack cohérente : Prometheus (métriques/alertes, taux de soft/hard block), Tempo (traces), Loki + Fluent Bit (journaux des qualifications). Couche 03 optionnelle/scaffold.
- Réserve : Tout 'À suivre' (rien de 'Sélectionné' en observabilité). RÉSERVE LICENCE : Grafana/Loki/Tempo AGPL-3.0 (non bloquant POC) — replis Apache : VictoriaLogs (logs), Coroot (APM eBPF). Journaux à cardinalité maîtrisée et anonymisés ; le masquage runtime des secrets/PII n'est PAS outillé (voir lacunes).

### Hygiène secrets — détection de fuite dans le code/historique (complément au coffre)
- **Choix : Gitleaks** _(Sélectionné)_
- Rôle : Seul outil de secret-scanning RETENU (MIT) : empêche la fuite de secrets en pre-commit/CI. Contrôle d'exploitation légitime. Alternatives : detect-secrets (À suivre), TruffleHog (À suivre, AGPL).
- Réserve : Gitleaks DÉTECTE les fuites, ne GÈRE/STOCKE pas les secrets — ce n'est PAS un coffre (voir lacunes : coffre 'En attente').

### Contrôleur de parcours / frontière de crawl priorisée (priorité, profondeur, domaine, budgets, fraîcheur)
- **Choix : Frontera** _(À suivre)_
- Rôle : Se branche sur Scrapy et comble le 'gérer la stratégie de visite' (blueprint §6) : frontier priorisée, breadth/depth-first, découverte, détection de cycles, budgets.
- Réserve : Frontera 'Ralenti' (pérennité 2). Pour un parcours simple au POC, la file/ordonnancement natif de Scrapy (Sélectionné) suffit — n'introduire Frontera que si la stratégie de visite le justifie. Orchestre le PARCOURS (priorité/profondeur/budgets).

## Cascade d'escalade — disponible au POC

> Au POC, l'évasion / le furtif / les unlockers managés / les solveurs CAPTCHA sont AUTORISÉS et font partie de la cascade disponible. Sécurité / légalité / RGPD = questions pour plus tard (phase pré-production).

- **curl_cffi / curl-impersonate (lexiforest fork) / primp / rnet / noble-tls / hrequests / bogdanfinn-tls-client / utls** — Impersonation TLS/JA3 et empreinte d'un navigateur précis. curl_cffi (À suivre) couvre compat protocole ET impersonation de la détection ; disponible au POC en complément de httpx/niquests.
- **playwright-stealth / Patchright / rebrowser-playwright / undetected-chromedriver / nodriver / zendriver / DrissionPage (mode furtif) / botasaurus / Camoufox / CloakBrowser** — Navigateurs furtifs / patches anti-détection. Plusieurs sont 'À suivre' (Patchright, zendriver, DrissionPage, botasaurus, rebrowser-playwright, CloakBrowser) ou 'En attente' (Camoufox, nodriver, undetected-chromedriver) : disponibles au POC pour le furtif au-dessus de Playwright.
- **SeleniumBase 'CDP Mode' / pydoll 'humanize=True'** — Les outils sont Sélectionné ; leurs modes anti-bot / humanisation comportementale sont activables au POC selon le besoin.
- **Bright Data / Scrapfly / ZenRows / Oxylabs / ScraperAPI (unlockers managés)** — Unlockers managés (rotation proxy/identité, résolution de challenge). Refusé au référentiel mais disponibles au POC pour les cibles les plus protégées.
- **2Captcha / CapSolver / CapMonster / Anti-Captcha / noCaptchaAI / ddddocr / Cloudflyer / hcaptcha-challenger / NopeCHA / Buster** — Solveurs de CAPTCHA. SaaS Refusé (2Captcha, CapSolver) ou solveurs 'En attente' (ddddocr) / 'À suivre' (Cloudflyer) — disponibles au POC quand un défi doit être franchi.
- **FlareSolverr / cloudscraper** — Contournement de challenge Cloudflare/anti-bot. 'À suivre' au référentiel — disponibles au POC.
- **Trafilatura / newspaper4k / jusText / python-readability / readability / MarkItDown / Resiliparse / crawl4ai / Firecrawl / ScrapeGraphAI** — Extraction métier / interprétation du sens. L'extraction métier vit plutôt en aval (note neutre). NB états : newspaper4k 'Sélectionné', crawl4ai/Trafilatura 'À suivre', Firecrawl 'Refusé'.
- **browser-use / Stagehand / Skyvern / Scrapling** — Agents LLM d'extraction / découverte d'actions par IA — relèvent de l'IA produit ; l'extraction métier vit plutôt en aval (note neutre). Le scoring d'actions sans sélecteur (§11) peut s'appuyer sur les locators Playwright. NB état : Scrapling 'Sélectionné'.
- **Selenium / Puppeteer / pycurl / Crawlee / Redis / etcd / MinIO (cible) / Scrapy-Redis** — Refusé au référentiel (Selenium, Puppeteer, pycurl, Crawlee, Redis, etcd) ou évincés par doublon/licence : à ne jamais recommander. MinIO 'À suivre' mais évincé (AGPL gênant, communauté archivée) au profit de Ceph RGW ; Scrapy-Redis 'En attente', peu utile au POC.

## Lacunes (non couvert par le référentiel)

- **Modèle de capture 'HttpExchange' natif (req/resp brut + timings + contexte réseau) + dépôt Ceph RGW raw/** — Aucun outil ne produit le format HttpExchange du blueprint : warcprox/warcio/pywb écrivent du WARC. Le mapping WARC→HttpExchange et le dépôt raw/ sont à coder. De plus aucun capteur HTTP brut n'est 'Sélectionné' (warcprox/pywb 'En attente', GPL).
- **Coffre à secrets (résolution d'identifiants, re-résolution à la reprise, masquage des journaux)** — TOUS les coffres sont 'En attente' (OpenBao, Vault, Infisical, SOPS — sécurité/IAM = phase pré-production). Au POC : variables d'environnement / fichiers Compose. Gitleaks détecte mais ne stocke pas.
- **Contrôle des sorties (egress) / anti-SSRF / DNS pin-né anti-rebinding** — Point de sécurité = phase pré-production : aucun outil ne filtre les adresses résolues (plages privées/loopback/link-local, métadonnées cloud 169.254.169.254), allowlist domaines/réseaux, ni revalidation après redirection. Pas de résolveur DNS dédié pour résoudre→valider l'IP→connecter sur cette IP. À traiter le moment venu au-dessus du client HTTP (CrowdSec/WAF protègent NOTRE site, pas les sorties).
- **Bibliothèque de hachage / empreinte de contenu (dédup, validation technique)** — Brique CENTRALE absente : aucun hash au référentiel (hashlib non explicité, blake3/xxhash absents). hashlib SHA-256 (stdlib) couvre sans dépendance ; ajouter blake3/xxhash si dédup haute vitesse requise.
- **Détection de type de contenu (MIME par magic numbers) et de charset/encodage** — Aucun outil de sniffing : python-magic/puremagic/filetype absents (type réel), chardet/charset-normalizer/cchardet absents (charset). Au-delà du Content-Type HTTP déclaré et de l'encodage exposé par lxml/selectolax, la vérification technique réelle n'est pas outillée.
- **Cache HTTP conditionnel clé-en-main (politique de fraîcheur, expiration, invalidation, store des validateurs)** — Aucune lib de cache HTTP (Hishel/CacheControl/requests-cache absents). httpx émet les en-têtes conditionnels mais toute la politique est à coder (le store des validateurs peut aller dans Valkey/Postgres).
- **Client S3 / couche d'accès au stockage objet pour écrire dans Ceph RGW raw/** — Aucun client S3 Python concret (boto3/s3fs/minio-py absents) ; seul OpenDAL (À suivre) approche l'abstraction. Un client S3 concret reste à acter pour matérialiser les sorties.
- **Classification du BLOCK SUBI en sortie (soft vs hard : refus persistant, IP bloquée, contenu incomplet, throttling vs lenteur) + niveau de confiance + cause alternative** — Pas d'outil dédié à la classification 'côté client sortant' (fichier 05 §2/§3) : CrowdSec détecte des attaquants ENTRANTS. Détecteur/qualificateur à CODER au-dessus des briques honnêtes (httpx/Playwright).
- **Moteur de POLITIQUE de réaction gouvernée (respecter/ralentir/replanifier/suspendre/arrêter/escalader selon qualification)** — Logique métier de décision non portée par aucun outil (OPA/Cerbos 'En attente', conçus pour l'autorisation applicative). Dagster orchestre l'EXÉCUTION, l'arbre de politique reste à coder (fichier 05 §4).
- **Machine d'état du cycle de vie (Created→Validated→…→Published, §3) + file de tâches DURABLE (réservation/bail TTL, ack, file différée+backoff, DLQ, backpressure)** — Aucune state-machine au référentiel (transitions/python-statemachine absents) → Pydantic + table de transitions Postgres. Le socle n'offre qu'un broker (Valkey) + un pool (Celery), pas une file durable (pgmq/RabbitMQ/SQS-like) : garanties bail/DLQ/réconciliation à construire ou via moteur durable (Temporal/Hatchet/DBOS — tous À suivre/En attente).
- **Disjoncteur (circuit breaker) par source + budget de tentatives/backoff+jitter (garde-fous §7)** — Aucune lib de résilience au référentiel (pybreaker/tenacity/resilience4j absents). À implémenter en code applicatif.
- **Garde-fous anti-bombe-zip / limites de stream / quarantaine de contenu malveillant** — Limites taille compressée-décompressée et durée max de réponse = code applicatif sur httpx (pas un outil). AUCUN antivirus/scanner de contenu malveillant (ClamAV absent) pour le 'téléchargement malveillant' (fichier 07 §4).
- **Isolation OS-level du navigateur (sandbox processus / gVisor / Firejail / conteneur durci)** — AUCUN outil de sandboxing au-delà des contextes éphémères de Playwright. L'isolation repose sur Docker/Compose + profil éphémère ; durcissement à combler en phase pré-production.
- **Gestionnaire de téléchargement robuste (reprise sur coupure, multi-connexion, checksum intégré) et client/transfert SFTP** — Aucun downloader dédié (aria2/wget/yt-dlp absents) : couvert par défaut via httpx/requests/aiohttp ou FilesPipeline Scrapy, sans brique résiliente. Aucun client SFTP au référentiel (handler 'downloaders' SFTP de CLAUDE.md non outillé).
- **Masquage/anonymisation runtime des secrets et PII dans les journaux** — Presidio 'En attente' (sécurité/IAM = phase pré-production) ; aucun outil 'Sélectionné'. Sujet pour plus tard (phase pré-production).
- **Rate limiting / concurrence par source + bus d'événements + coordination distribuée (scale-out)** — Pas d'outil dédié de rate-limit par source (Scrapy AutoThrottle pour le crawl ; sinon sémaphores / Temporal — brique applicative). Aucun bus 'Sélectionné' (NATS À suivre ; Postgres LISTEN/NOTIFY au POC). La coordination distribuée (leader-election/locks) est **portée par Temporal** si besoin ; etcd reste hors besoin de l'architecture actuelle.

## Anomalies relevées par le garde-fou

- ANOMALIE D'ÉTAT : newspaper4k et Scrapling sont 'Sélectionné' au référentiel ; ce sont des outils d'EXTRACTION/agent LLM, dont l'extraction métier vit plutôt en aval. État 'Sélectionné' probablement justifié pour un module d'extraction AVAL distinct — à dissocier par module pour éviter les confusions.
- AUCUN client HTTP n'est 'Sélectionné' : httpx, niquests, aiohttp et requests sont TOUS 'À suivre'. Or le client HTTP est la brique la plus fondamentale et omniprésente du module (moteurs, session/réseau, détection, validation, cache). httpx mérite une promotion à 'Sélectionné' — incohérence de maturité du socle.
- INCOHÉRENCE D'USAGE CrowdSec : 'Sélectionné' et recommandé pour qualifier les blocks, mais son cas d'usage natif est la défense de NOTRE infra (attaquants entrants), pas la classification des blocks que le collecteur SUBIT en sortie. Le besoin réel (classification soft/hard du block sortant) n'a aucun outil adéquat — recommandation à requalifier comme 'réemploi à valider', pas comme couverture native.
- OUTILLAGE SÉCURITÉ DIFFÉRÉ : le cloisonnement des secrets (checkpoints sans secret en clair, re-résolution à la reprise — fichier 07) et l'anti-SSRF/egress (§4) n'ont aucun outillage 'Sélectionné' ('En attente' : OpenBao/Vault/Infisical/SOPS/Presidio). Sécurité = phase pré-production ; au POC, aucune contrainte (variables d'environnement / fichiers Compose suffisent).
- DOUBLON DE BROKER/CACHE NON TRANCHÉ : Valkey ('À suivre') est simultanément proposé comme broker Celery, store de session partagé, cache de version (validateurs ETag) et file différée — mais reste non verrouillé et concurrencé par PostgreSQL (file façon Hatchet) et NATS/JetStream. Le socle n'a aucun broker 'Sélectionné' : dépendance structurante (Celery en a besoin) laissée ouverte.
- DÉPENDANCE WARC vs CONTRAT HttpExchange : tous les outils d'archivage HTTP (warcio À suivre, warcprox/pywb En attente) écrivent du WARC, format qui NE correspond PAS au modèle HttpExchange propre du blueprint. La capacité 'capture HTTP brute' (composant transverse central, hub §5) n'a donc aucun outil produisant directement le contrat — couverture partielle masquée par la présence des outils WARC.
- OUTILS DE FURTIF/CONTOURNEMENT 'RECOMMANDABLES' : de nombreux navigateurs furtifs/contournement sont 'À suivre' (Patchright, zendriver, DrissionPage, botasaurus, rebrowser-playwright, CloakBrowser, cloudscraper, FlareSolverr, Cloudflyer, hrequests, curl-impersonate) — états qui les rendent recommandables par les règles normales du référentiel et disponibles dans la cascade au POC.
