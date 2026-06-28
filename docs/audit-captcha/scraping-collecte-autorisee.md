# Inventaire d'audit — Collecte web et automatisation (scraping autorisé)

> **Sujet** : outils de collecte web, crawlers IA/LLM et agents navigateur. Distinct des CAPTCHA.
> **Statut** : inventaire d'audit fournisseur (présélection) — **complété par** la stratégie courante [`strategie-anti-bot.md`](../strategie-anti-bot.md) et le blueprint [`00-hub.md`](../00-hub.md).
>
> ⏸️ **Posture actuelle (supersede le cadrage ci-dessous)** : **au POC, AUCUNE contrainte** (sécurité, légalité, RGPD, `robots.txt`, CGU, autorisation). Ces sujets **dépendent des pays cibles** et sont traités dans une **phase dédiée AVANT la production**. Les mentions « collecte autorisée uniquement / cadre impératif / base légale / garde-fous obligatoires » de ce document relèvent de **cette phase**, **pas du POC**.

## Provenance du relevé

| Attribut | Valeur |
|---|---|
| Date et heure de collecte | **2026-06-22T21:06:41Z** (UTC) |
| Source | GitHub REST API v3 (authentifiée) |
| Empreinte (SHA-256, 16c) | `c23b51c832345b6c` |
| Données brutes | `scraping-audit-raw.json` (joint) |

---

## 1. Synthèse exécutive

Le paysage a basculé vers l'**IA** : aux crawlers classiques (Scrapy, Colly) s'ajoutent désormais des convertisseurs web→LLM (Firecrawl, Crawl4AI), des extracteurs sémantiques par prompt (ScrapeGraphAI) et des agents navigateur autonomes (Browser Use, Stagehand). Ces derniers concentrent le **risque le plus élevé** : ils exécutent des actions multi-étapes pilotées par LLM, donc sensibles à l'injection d'instructions présentes dans les pages.

**Constats tirés des données** :

- **Popularité massive et récente** : `firecrawl` (137 k★) et `browser-use` (100 k★) dominent — projets très jeunes mais en croissance explosive, signe d'adoption mais aussi de maturité de sécurité encore à éprouver.
- **Licences à encadrer** : `firecrawl` et `nodriver` en **AGPL-3.0** (impact SaaS) ; `undetected-chromedriver` en GPL-3.0. Les références d'automatisation (Playwright, Puppeteer, Selenium, Scrapy, Colly, Crawlee, Katana) sont permissives.
- **Risque par catégorie** : les agents autonomes (Browser Use, Stagehand) sont **critiques** ; les convertisseurs LLM (Firecrawl, Crawl4AI, ScrapeGraphAI) **élevés** ; les automatisations classiques **moyennes**. Les outils anti-détection (undetected-chromedriver, nodriver) sont réservés au laboratoire.
- `fingerprintjs/BotD` figure ici comme **outil défensif** : à utiliser pour mesurer la détectabilité de vos propres collectes.

---

## 2. Tableau offensif — collecte et audit autorisés

Légende maintenance : 🟢 active · 🟡 ralentie/faible · 🔴 dormante · ⚫ archivée.

| N° | Dépôt | ★ | Forks | Contrib | Maintenance | Comm. 90j | Releases/an | Licence | Compat. proprio | Catégorie | Approche IA | SEC | Adv | Décision |
|--:|--|--:|--:|--:|--|--:|--:|--|--|--|--|--|--:|--|
| 1 | [firecrawl/firecrawl](https://github.com/firecrawl/firecrawl) | 137 123 | 7 955 | 150 | 🟢 Active | 557 | 16 | AGPL-3.0 | Risque SaaS fort (copyleft réseau) | Crawl → Markdown/JSON | Extraction LLM/RAG | — | 2 | Élevé ; RAG après revue AGPL |
| 2 | [browser-use/browser-use](https://github.com/browser-use/browser-use) | 100 115 | 11 154 | 315 | 🟢 Active | 782 | 75 | MIT | Compatible (permissive) | Agent navigateur | Multi-LLM (GPT/Claude/Gemini/local) | ✓ | 1 | Critique ; isolé + domaines autorisés |
| 3 | [puppeteer/puppeteer](https://github.com/puppeteer/puppeteer) | 95 197 | 9 462 | 446 | 🟢 Active | 231 | 100 | Apache-2.0 | Compatible (permissive) | Automatisation Chrome/FF | IA externe via MCP | ✓ | 0 | Moyen ; scénarios Chromium |
| 4 | [microsoft/playwright](https://github.com/microsoft/playwright) | 91 410 | 5 953 | 470 | 🟢 Active | 839 | 16 | Apache-2.0 | Compatible (permissive) | Automatisation multi-nav. | Intégrable agents/MCP | ✓ | 0 | Moyen ; référence audit reproductible |
| 5 | [unclecode/crawl4ai](https://github.com/unclecode/crawl4ai) | 69 285 | 7 076 | 76 | 🟢 Active | 70 | 15 | Apache-2.0 | Compatible (permissive) | Crawler LLM/RAG | Markdown LLM-ready, stratégies LLM | ✓ | 11 | Élevé ; RAG auto-hébergé |
| 6 | [scrapy/scrapy](https://github.com/scrapy/scrapy) | 62 460 | 11 681 | 373 | 🟢 Active | 138 | 9 | BSD-3-Clause | Compatible (permissive) | Framework crawler | IA externe via pipelines | ✓ | 11 | Moyen ; référence collecte structurée |
| 7 | [SeleniumHQ/selenium](https://github.com/SeleniumHQ/selenium) | 34 212 | 8 683 | 405 | 🟢 Active | 405 | 13 | Apache-2.0 | Compatible (permissive) | Automatisation navigateur | IA externe | — | 0 | Moyen ; mature mais lourd |
| 8 | [ScrapeGraphAI/Scrapegraph-ai](https://github.com/ScrapeGraphAI/Scrapegraph-ai) | 27 414 | 2 589 | 107 | 🟢 Active | 28 | 36 | MIT | Compatible (permissive) | Extraction sémantique | Prompts LLM + graphes | ✓ | 0 | Élevé ; coût/précision/fuite données |
| 9 | [gocolly/colly](https://github.com/gocolly/colly) | 25 340 | 1 853 | 114 | 🟢 Active | 23 | 0 | Apache-2.0 | Compatible (permissive) | Crawler HTTP Go | Aucune IA native | — | 0 | Moyen ; collectes rapides sans JS |
| 10 | [apify/crawlee](https://github.com/apify/crawlee) | 23 971 | 1 457 | 120 | 🟢 Active | 122 | 10 | Apache-2.0 | Compatible (permissive) | Crawl HTTP/navigateur | Données LLM/RAG ; IA externe | — | 0 | Élevé ; sessions/proxy/fingerprints |
| 11 | [browserbase/stagehand](https://github.com/browserbase/stagehand) | 23 201 | 1 588 | 40 | 🟢 Active | 184 | 49 | MIT | Compatible (permissive) | SDK agents navigateur | Actions/extraction langage naturel | — | 0 | Critique ; limiter domaines/secrets |
| 12 | [projectdiscovery/katana](https://github.com/projectdiscovery/katana) | 17 070 | 1 146 | 62 | 🟢 Active | 124 | 8 | MIT | Compatible (permissive) | Spidering / découverte URL | Aucune IA native | ✓ | 0 | Élevé ; ASM/pentest autorisé |
| 13 | [ultrafunkamsterdam/undetected-chromedriver](https://github.com/ultrafunkamsterdam/undetected-chromedriver) | 12 702 | 1 337 | 11 | 🟡 Ralenti | 1 | 0 | GPL-3.0 | Incompatible distribution propriétaire | Anti-détection | Aucune IA native | — | 0 | Critique ; laboratoire uniquement |
| 14 | [ultrafunkamsterdam/nodriver](https://github.com/ultrafunkamsterdam/nodriver) | 4 384 | 414 | 3 | 🟡 Faible | 6 | 0 | AGPL-3.0 | Risque SaaS fort (copyleft réseau) | Automatisation CDP | Aucune IA native | — | 0 | Critique ; laboratoire uniquement |
| 15 | [fingerprintjs/BotD](https://github.com/fingerprintjs/BotD) | 1 428 | 99 | 18 | 🟢 Active | 15 | 1 | MIT | Compatible (permissive) | Détection / banc d'essai | Identification frameworks auto | — | 0 | Mesurer la détectabilité |

### Typologie des outils

| Famille | Projets | Usage recommandé |
|---|---|---|
| **Conversion web → données LLM** | Firecrawl, Crawl4AI | RAG, indexation, Markdown propre |
| **Extraction sémantique par prompt** | ScrapeGraphAI, Stagehand | JSON selon schéma, DOM changeant |
| **Agents navigateur autonomes** | Browser Use, Stagehand | Parcours multi-étapes contrôlés |
| **Crawlers industriels** | Scrapy, Crawlee, Colly | Volumétrie, reprise sur erreur, pipelines |
| **Automatisation navigateur** | Playwright, Puppeteer, Selenium | Pages JS, tests E2E reproductibles |
| **Spidering sécurité** | Katana | Cartographie de surface d'attaque autorisée |
| **Anti-détection** | undetected-chromedriver, nodriver | Tester la robustesse anti-bot interne |

---

## 3. Architecture recommandée — collecte conforme *(cible pré-production)*

> ⏸️ **Différé — phase pré-production.** Les contrôles ci-dessous (`robots.txt` / CGU / base légale, allowlist,
> budget de requêtes, coffre de secrets, scan PII, rétention) **ne s'appliquent PAS au POC** (cf. bandeau en tête).
> Ils décrivent la **cible** d'un déploiement conforme, à instruire dans la phase dédiée **avant production**
> (dépend des pays cibles). Au POC, la collecte est **libre, sans aucun de ces garde-fous**.

```
Registre des sources autorisées
        |
        v
Orchestrateur de collecte
        +--> HTTP : Scrapy / Colly / Crawlee
        +--> Navigateur : Playwright / Puppeteer
        +--> IA : Firecrawl / Crawl4AI / ScrapeGraphAI
        |
        v
Contrôles pré-exécution
        +--> robots.txt / CGU / base légale
        +--> allowlist domaines et chemins
        +--> budget de requêtes et concurrence
        +--> coffre de secrets et comptes dédiés
        |
        v
Zone brute chiffrée et horodatée
        |
        v
Normalisation / déduplication / scan PII
        |
        v
Catalogue de données + traçabilité
        |
        v
RAG / analytics / archivage avec rétention
```

---

## 4. Garde-fous agents IA *(cible pré-production)*

> ⏸️ **Différé — phase pré-production.** Au POC, **aucun de ces garde-fous n'est imposé** (cf. bandeau en tête) :
> l'autonomie, l'évasion et l'extraction sont **libres**. La liste ci-dessous est la **cible** d'un encadrement
> de production, à activer dans la phase dédiée **avant production**.

Pour un déploiement en production, les agents navigateur autonomes (Browser Use, Stagehand) appelleront un encadrement strict :

- allowlist stricte des domaines et des actions ;
- refus des téléchargements exécutables et des changements de compte ;
- secrets éphémères, profils de navigateur dédiés, aucune session personnelle ;
- validation humaine avant achat, publication, envoi de formulaire ou suppression ;
- limites de profondeur, volume, concurrence et durée ;
- journalisation des prompts, URL, actions, réponses et données extraites ;
- filtrage des instructions malveillantes dans les pages (prompt injection) ;
- classification et suppression des données personnelles non nécessaires ;
- bouton d'arrêt et révocation immédiate des jetons.

---

## 5. Analyse juridique (soumise à validation)

| Licence | Dépôts | Implication |
|---|---|---|
| **AGPL-3.0** | `bunkerity/bunkerweb`, `firecrawl/firecrawl`, `ultrafunkamsterdam/nodriver` | Copyleft réseau : impact SaaS direct, obligation de fournir le code source. Revue avant usage RAG/production. |
| **GPL-3.0** | `chaitin/SafeLine`, `fail2ban/fail2ban`, `ultrafunkamsterdam/undetected-chromedriver` | Incompatible distribution propriétaire. |
| **Permissive** (MIT, Apache-2.0, BSD) | majorité | Intégration possible avec attribution. |

Note : `firecrawl` (AGPL) est souvent retenu pour RAG malgré la licence — la revue doit trancher l'usage interne vs distribution.

---

---

## 6. Focus outils IA — caractérisation objective (sans « agressivité »)

Les six outils IA de la liste relèvent en réalité de **quatre familles distinctes** qu'il ne faut pas confondre : moteurs de crawl/extraction (Firecrawl, Crawl4AI), extraction sémantique par LLM (ScrapeGraphAI), agents de navigation (Browser Use, Stagehand) et framework d'orchestration (Crawlee).

La notion de « niveau d'agressivité IA » est trompeuse : **un outil n'est pas agressif par nature**. L'impact réel dépend de la concurrence, du débit, du rendu JavaScript, de la profondeur, des proxies et de l'autonomie accordée à l'agent. On la remplace par des attributs mesurables.

| N° | Dépôt | ★ | Type | Autonomie IA | Mode | Aptitude volume | Déterminisme | Usage recommandé |
|--:|--|--:|--|--|--|--|--|--|
| 1 | `firecrawl/firecrawl` | 137 123 | Plateforme / API | Élevée | Navigateur | Élevé | Moyen | API collecte mutualisée, RAG |
| 2 | `browser-use/browser-use` | 100 115 | Agent navigateur | Très élevée | Agent | Faible | Faible | Parcours inconnus multi-étapes |
| 3 | `unclecode/crawl4ai` | 69 285 | Bibliothèque Python | Moyenne | Navigateur | Moyen à élevé | Moyen à élevé | Extraction auto-hébergée Python |
| 4 | `ScrapeGraphAI/Scrapegraph-ai` | 27 414 | Extraction LLM | Élevée | Selon pipeline | Faible à moyen | Faible | Extraction sémantique complexe |
| 5 | `apify/crawlee` | 23 971 | Framework crawler | Faible / native inexistante | HTTP + navigateur | Très élevé | Élevé | Crawl industriel, orchestration |
| 6 | `browserbase/stagehand` | 23 201 | Agent hybride | Élevée | Agent + code | Faible à moyen | Moyen | Parcours métier adaptatifs |

### Attributs à utiliser pour qualifier l'impact (en remplacement de « agressivité »)

`Autonomie IA` · `Mode : HTTP / navigateur / agent` · `Concurrence maximale` · `Profondeur de crawl` · `Capacité d'interaction` · `Usage de proxies` · `Déterminisme` · `Coût LLM` · `Risque opérationnel` · `Aptitude au crawl massif`.

### Avis par outil

**`firecrawl/firecrawl` — plateforme de collecte prête pour les agents.** Crawl, recherche, mapping, traitement par lots ; sorties Markdown/HTML/captures/JSON ; endpoint agent pour recherches autonomes ; SDK Python/Node/Java. Adapté à une **API mutualisée de collecte pour pipelines RAG**. Ne pas confondre le dépôt auto-hébergeable avec l'offre hébergée complète. La licence **AGPL-3.0** impose une revue juridique pour tout usage SaaS ou modification exposée par le réseau. → **Production prioritaire** après revue licence et tests de charge.

**`unclecode/crawl4ai` — bibliothèque Python pour contenus LLM-ready.** Très bonne intégration Python, contrôle fin navigateur/extraction, Markdown RAG, deep crawling, licence **Apache-2.0** permissive. **Point d'audit critique vérifié** : le projet a publié en juin 2026 de nombreuses advisories — **5 critiques** (RCE pré-auth, sandbox escape AST, écriture de fichiers) et **6 high** (SSRF multiples, exfiltration de credentials LLM, injection d'arguments Chromium), dont certaines datées du 18 juin 2026. La réactivité du projet est un bon signe, mais cela **impose de déployer uniquement une version corrigée, avec l'API Docker durcie et les paramètres sécurisés par défaut**. → **Meilleur choix auto-hébergeable Python**, sous condition de durcissement strict du serveur Docker.

**`ScrapeGraphAI/Scrapegraph-ai` — extraction sémantique pilotée par LLM.** On définit l'information attendue plutôt que des sélecteurs rigides ; extraction selon un schéma ; adaptation aux variations HTML ; licence **MIT**. Limites : consommation de jetons, latence, résultats non strictement déterministes, risque d'hallucination ou de mauvaise association de champs, peu adapté au crawl massif. → **Couche d'extraction intelligente après une collecte déterministe**, pas moteur de crawl industriel. Retenir pour pages hétérogènes ou faible volume.

**`browser-use/browser-use` — agent autonome contrôlant un navigateur.** Adapté aux parcours nécessitant navigation multi-étapes, clics/formulaires, raisonnement sur l'état visuel ou le DOM, récupération après erreur, adaptation à des interfaces inconnues. **Pas** l'outil pour extraire dix millions de pages : plus de coût, de latence et de non-déterminisme qu'un crawler classique. **Risque opérationnel le plus élevé** si domaines, actions et secrets ne sont pas strictement bornés. → **Laboratoire et workflows complexes**, pas crawl massif.

**`browserbase/stagehand` — automatisation hybride, entre Playwright et agent autonome.** Probablement le meilleur compromis de la liste pour des parcours métier contrôlés : code déterministe pour les étapes connues, langage naturel pour les pages variables, extraction structurée, prévisualisation et mise en cache d'actions, repli possible vers une exécution sans inférence LLM. Plus orienté **fiabilisation d'automatisations en production** que Browser Use. Licence **MIT**. → **Retenir pour l'automatisation adaptative de parcours connus**.

**`apify/crawlee` — framework industriel de crawling.** Crawlers HTTP et navigateur ; intégration Playwright/Puppeteer ; files d'URL ; sessions, stockage, rotation de proxies ; contrôle de concurrence ; licence **Apache-2.0**. Pas un outil IA en soi : c'est la **fondation déterministe et scalable** à laquelle ajouter une extraction LLM. Le dépôt principal cible Node.js/TypeScript ; Crawlee for Python est un projet séparé. → **Meilleur socle pour un crawler industriel maîtrisé**.

### Classement par besoin

| Besoin | Choix recommandé |
|---|---|
| Collecte industrielle contrôlée | **Crawlee** |
| Pipeline Python auto-hébergé | **Crawl4AI** (durci) |
| API transverse pour RAG et agents | **Firecrawl** |
| Extraction sans sélecteurs fixes | **ScrapeGraphAI** |
| Parcours adaptatifs mais contrôlés | **Stagehand** |
| Agent autonome exploratoire | **Browser Use** |

### Architecture en cascade — minimiser coût LLM et exposition

La meilleure architecture ne consiste pas à n'en choisir qu'un seul, mais à hiérarchiser du déterministe vers le coûteux :

```
Crawlee ou Crawl4AI
        |
        v
collecte déterministe
        |
        +--> extraction CSS / XPath
        |
        +--> ScrapeGraphAI ou LLM
        |    uniquement en cas d'échec
        |
        +--> Stagehand
             uniquement pour les parcours interactifs
```

Cette hiérarchie réduit les coûts LLM, améliore la reproductibilité et limite l'exposition opérationnelle des agents autonomes. La règle : **n'escalader vers l'IA que lorsque le déterministe échoue**.

---

## 7. Décision d'architecture

| Niveau | Projets |
|---|---|
| **Référence audit reproductible** | Playwright, Scrapy |
| **Collecte rapide sans JS** | Colly, Crawlee |
| **RAG / web→LLM (après revue AGPL)** | Firecrawl, Crawl4AI |
| **Extraction sémantique (évaluer coût/fuite)** | ScrapeGraphAI |
| **Agents autonomes (isolé + garde-fous)** | Browser Use, Stagehand |
| **ASM / pentest autorisé** | Katana |
| **Laboratoire anti-détection uniquement** | undetected-chromedriver, nodriver |
| **Banc de détectabilité** | BotD |

> Conditions **différées en phase pré-production** (PAS au POC, cf. bandeau en tête) : (1) validation juridique (AGPL en priorité), (2) garde-fous agents IA du §4, (3) base légale de collecte documentée par source. Au POC, la sélection d'outils se fait **sans ces conditions**.
