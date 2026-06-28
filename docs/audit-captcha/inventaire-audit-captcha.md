# Inventaire d'audit — Dépôts CAPTCHA et écosystème associé

> **Statut du document** : Inventaire d'audit fournisseur — exploitable pour présélection, cadrage et instruction de décision d'architecture.
> **Ce que ce document permet** : comparaison multicritère (popularité, maintenance, sécurité, licence, qualification technique).
> **Ce qu'il ne remplace pas** : l'homologation sécurité finale (qui exige le score OpenSSF Scorecard et l'analyse des dépendances transitives, non collectés ici) et le benchmark de performance (qui exige une exécution en laboratoire — voir §9).

## Provenance et traçabilité du relevé

| Attribut | Valeur |
|---|---|
| Date et heure de collecte | **2026-06-22T18:55:53Z** (fuseau UTC) |
| Source | GitHub REST API v3 (authenticated) |
| Nombre de dépôts | 44 |
| Empreinte du relevé (SHA-256, 16c) | `eb6e92d59774e616` |
| Données brutes | `captcha-audit-raw.json` (joint) |
| Tableau maître 30 colonnes | `captcha-audit-master.csv` (joint, UTF-8 BOM, ouvrable Excel) |

Les colonnes chiffrées (étoiles, forks, contributeurs, issues/PR, commits 30/90/365j, releases, archivé, advisories, SECURITY.md, Dependabot/Renovate, CI) proviennent directement de l'API GitHub authentifiée à l'horodatage ci-dessus. Les colonnes de qualification technique (déploiement, observabilité, HA, challenge, WCAG, vie privée) proviennent de la documentation de chaque projet et sont à confirmer en revue.

---

## 1. Synthèse exécutive

Les 44 dépôts couvrent quatre familles : **Défense** (WAF, anti-bot, alternatives CAPTCHA), **Analyse/OCR** (baseline de robustesse), **Laboratoire offensif** (solveurs, anti-détection — recommandé en environnement isolé) et **Industrialisation** (automatisation, métrologie, accessibilité).

**Constats structurants tirés des données collectées** :

- **Risque de mainteneur unique** : 5 dépôts ont ≤ 2 contributeurs effectifs (`altcha-org/altcha`, `wenlng/go-captcha`, `dessant/buster`, `lining0806/PythonSpiderNotes`, `zhaipro/easy12306`). Pour `altcha-org/altcha`, ce chiffre reflète un développement centralisé mais le projet reste très actif ; pour les autres, c'est un signal de fragilité.
- **Maintenance faible ou dormante** : 15 dépôts montrent une activité résiduelle. La quasi-totalité des solveurs offensifs et plusieurs CAPTCHA de niche en font partie.
- **Hygiène sécurité faible** : seulement **13/44** dépôts publient un `SECURITY.md`. Aucun score OpenSSF Scorecard n'a pu être collecté (hôte hors allowlist réseau — voir §10).
- **Licences à fort impact** : 4 dépôts en **AGPL-3.0** (`bunkerity/bunkerweb`, `mCaptcha/mCaptcha`, `ultrafunkamsterdam/nodriver`, `grafana/k6`) déclenchent le copyleft réseau (impact SaaS direct) ; 4 en **GPL-3.0** (`chaitin/SafeLine`, `ultrafunkamsterdam/undetected-chromedriver`, `dessant/buster`, `QIN2DIM/hcaptcha-challenger`) sont incompatibles avec une distribution propriétaire ; 2 **sans licence OSI** (`lining0806/PythonSpiderNotes`, `sarperavci/GoogleRecaptchaBypass`) sont par défaut « tous droits réservés ».
- **Advisories publiées** : 8 dépôts ont des advisories de sécurité GitHub, signe de processus de divulgation actif (et non d'insécurité) : `owasp-modsecurity/ModSecurity` (7), `prometheus/prometheus` (6), `TecharoHQ/anubis` (4), `mosparo/mosparo` (3), `bunkerity/bunkerweb` (2), `corazawaf/coraza` (2), `coreruleset/coreruleset` (2), `open-telemetry/opentelemetry-collector` (1).

> **Avertissement méthodologique** : toutes les conclusions juridiques (compatibilité de licence, impact SaaS, obligations de redistribution) sont des **analyses techniques soumises à validation juridique**, non des avis définitifs. Le classement par étoiles ne constitue jamais à lui seul une recommandation de mise en production.

---

## 2. Vues filtrées

Les quatre vues ci-dessous dérivent du même tableau maître. Légende maintenance : 🟢 active · 🟡 ralentie/faible · 🔴 dormante · ⚫ archivée.

### Vue 1 — Défense (WAF / anti-bot / alternatives CAPTCHA)

| # | Dépôt | ★ | Forks | Contrib | Maintenance | Comm. 90j | Release | Licence | Compat. proprio | SEC | Adv | Bot | CI |
|--|--|--|--|--|--|--|--|--|--|--|--|--|--|
| 1 | [chaitin/SafeLine](https://github.com/chaitin/SafeLine) | 21 549 | 1 412 | 21 | 🟡 Ralenti | 1 | v9.3.9 | GPL-3.0 | Incompatible distribution propriétaire | — | 0 | — | ✓ |
| 2 | [TecharoHQ/anubis](https://github.com/TecharoHQ/anubis) | 20 149 | 632 | 170 | 🟢 Active | 42 | v1.25.0 | MIT | Compatible (permissive) | ✓ | 4 | ✓ | ✓ |
| 3 | [bunkerity/bunkerweb](https://github.com/bunkerity/bunkerweb) | 10 641 | 621 | 48 | 🟢 Active | 336 | v1.6.12-rc3 | AGPL-3.0 | Risque SaaS fort (copyleft réseau) | ✓ | 2 | ✓ | ✓ |
| 4 | [owasp-modsecurity/ModSecurity](https://github.com/owasp-modsecurity/ModSecurity) | 9 680 | 1 734 | 97 | 🟢 Active | 87 | v3.0.15 | Apache-2.0 | Compatible (permissive) | ✓ | 7 | — | ✓ |
| 5 | [tiagozip/cap](https://github.com/tiagozip/cap) | 6 977 | 480 | 28 | 🟢 Active | 137 | standalone@3.1.5 | Apache-2.0 | Compatible (permissive) | — | 0 | ✓ | ✓ |
| 6 | [corazawaf/coraza](https://github.com/corazawaf/coraza) | 3 587 | 326 | 48 | 🟢 Active | 44 | v3.7.0 | Apache-2.0 | Compatible (permissive) | ✓ | 2 | ✓ | ✓ |
| 7 | [coreruleset/coreruleset](https://github.com/coreruleset/coreruleset) | 3 172 | 459 | 129 | 🟢 Active | 50 | v4.27.0 | Apache-2.0 | Compatible (permissive) | ✓ | 2 | ✓ | ✓ |
| 8 | [jeremykenedy/laravel-auth](https://github.com/jeremykenedy/laravel-auth) | 3 049 | 983 | 30 | 🟡 Ralenti | 1 | v11.1.0 | MIT | Compatible (permissive) | — | 0 | ✓ | ✓ |
| 9 | [mewebstudio/captcha](https://github.com/mewebstudio/captcha) | 2 577 | 462 | 57 | 🟡 Faible | 6 | 3.5.0 | MIT | Compatible (permissive) | — | 0 | — | — |
| 10 | [altcha-org/altcha](https://github.com/altcha-org/altcha) | 2 484 | 121 | 1 | 🟢 Active | 48 | v3.1.0 | MIT | Compatible (permissive) | ✓ | 0 | — | ✓ |
| 11 | [mCaptcha/mCaptcha](https://github.com/mCaptcha/mCaptcha) | 2 463 | 92 | 17 | 🟡 Ralenti | 1 | v0.1.0 | AGPL-3.0 | Risque SaaS fort (copyleft réseau) | — | 0 | ✓ | ✓ |
| 12 | [mojocn/base64Captcha](https://github.com/mojocn/base64Captcha) | 2 367 | 310 | 14 | 🟡 Ralenti | 1 | v1.3.8 | Apache-2.0 | Compatible (permissive) | — | 0 | — | ✓ |
| 13 | [wenlng/go-captcha](https://github.com/wenlng/go-captcha) | 2 342 | 216 | 1 | 🟡 Faible | 1 | v2.0.5 | Apache-2.0 | Compatible (permissive) | — | 0 | — | — |
| 14 | [markets/invisible_captcha](https://github.com/markets/invisible_captcha) | 1 245 | 67 | 23 | 🔴 Dormant | 1 | — | MIT | Compatible (permissive) | — | 0 | — | ✓ |
| 15 | [dromara/tianai-captcha](https://github.com/dromara/tianai-captcha) | 1 154 | 149 | 12 | 🟡 Faible | 1 | 1.5.5 | Apache-2.0 | Compatible (permissive) | — | 0 | — | — |
| 16 | [friendlycaptcha/friendly-challenge](https://github.com/friendlycaptcha/friendly-challenge) | 448 | 66 | 32 | 🟡 Faible | 3 | — | MIT | Compatible (permissive) | — | 0 | — | — |
| 17 | [prosopo/captcha](https://github.com/prosopo/captcha) | 295 | 9 | 17 | 🟢 Active | 215 | v3.6.46 | Apache-2.0 | Compatible (permissive) | — | 0 | ✓ | ✓ |
| 18 | [mosparo/mosparo](https://github.com/mosparo/mosparo) | 295 | 17 | 72 | 🟢 Active | 109 | v1.5.2 | MIT | Compatible (permissive) | ✓ | 3 | — | ✓ |

#### Qualification technique et fonctionnelle — solutions défensives

| # | Dépôt | Déploiement | Observabilité | HA | Challenge | WCAG | Vie privée | Svc ext. | Hors-ligne |
|--|--|--|--|--|--|--|--|--|--|
| 1 | SafeLine | Docker Compose | Partielle | Oui (multi-noeud) | — | — | — | — | — |
| 2 | anubis | Binaire, Docker, Helm | Prometheus + OTel | Stateless | — | — | — | — | — |
| 3 | bunkerweb | Docker, K8s, Helm, Autoconf | Prometheus | Oui | — | — | — | — | — |
| 4 | ModSecurity | Module Apache/Nginx | Via hôte | Selon hôte | — | — | — | — | — |
| 5 | cap | Docker, npm, standalone | Non native | Stateless | PoW | Bonne | Auto-hébergé | Non | Oui |
| 6 | coraza | Lib Go, Caddy/Traefik plugin | Via hôte | Selon hôte | — | — | — | — | — |
| 7 | coreruleset | Fichiers de règles | Via WAF | N/A | — | — | — | — | — |
| 8 | laravel-auth | App Laravel (démo) | Non | N/A | — | — | — | — | — |
| 9 | captcha | Composer (Laravel) | Non | Via app | Texte image | Faible | Auto-hébergé | Non | Oui |
| 10 | altcha | npm, widget JS, serveur Go | Non native | Stateless | PoW | AA | Auto-hébergé | Non | Oui |
| 11 | mCaptcha | Docker, binaire | Prometheus | Redis requis | PoW | Bonne | Auto-hébergé | Non | Oui |
| 12 | base64Captcha | Lib Go | Non | Store pluggable | Texte/audio | Moyenne | Auto-hébergé | Non | Oui |
| 13 | go-captcha | Lib Go, service HTTP/gRPC | Non native | Stateless | Clic/slide/rotation | Faible | Auto-hébergé | Non | Oui |
| 14 | invisible_captcha | Gem Ruby (Rails) | Non | Via app | Honeypot+temps | Excellente | Auto-hébergé | Non | Oui |
| 15 | tianai-captcha | JAR (Spring) | Non | Via app | Slide/clic/rotation | Faible | Auto-hébergé | Non | Oui |
| 16 | friendly-challenge | npm, widget JS | Non | Stateless (SaaS) | PoW | AA | SaaS (FR) | Oui | Non |
| 17 | captcha | npm, Docker | Partielle | Oui | Image/PoW | Moyenne | Décentralisé | Partiel | Partiel |
| 18 | mosparo | Docker, manuel | Non native | DB requise | Anti-spam invisible | Excellente | Auto-hébergé | Non | Oui |

---

### Vue 2 — Analyse / OCR / Robustesse ML

| # | Dépôt | ★ | Forks | Contrib | Maintenance | Comm. 90j | Licence | Compat. proprio | SEC | Adv | CI |
|--|--|--|--|--|--|--|--|--|--|--|--|
| 1 | [opencv/opencv](https://github.com/opencv/opencv) | 89 316 | 56 653 | 276 | 🟢 Active | 245 | Apache-2.0 | Compatible (permissive) | ✓ | 0 | ✓ |
| 2 | [PaddlePaddle/PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) | 83 300 | 10 843 | 284 | 🟢 Active | 66 | Apache-2.0 | Compatible (permissive) | — | 0 | ✓ |
| 3 | [tesseract-ocr/tesseract](https://github.com/tesseract-ocr/tesseract) | 74 887 | 10 670 | 196 | 🟢 Active | 55 | Apache-2.0 | Compatible (permissive) | — | 0 | ✓ |
| 4 | [JaidedAI/EasyOCR](https://github.com/JaidedAI/EasyOCR) | 29 646 | 3 578 | 115 | 🟡 Ralenti | 1 | Apache-2.0 | Compatible (permissive) | — | 0 | — |
| 5 | [albumentations-team/albumentations](https://github.com/albumentations-team/albumentations) | 15 314 | 1 709 | 166 | ⚫ Archivé | 1 | MIT | Compatible (permissive) | — | 0 | ✓ |
| 6 | [madmaze/pytesseract](https://github.com/madmaze/pytesseract) | 6 362 | 751 | 42 | 🔴 Dormant | 1 | Apache-2.0 | Compatible (permissive) | — | 0 | ✓ |
| 7 | [Trusted-AI/adversarial-robustness-toolbox](https://github.com/Trusted-AI/adversarial-robustness-toolbox) | 6 053 | 1 321 | 109 | 🟡 Ralenti | 1 | MIT | Compatible (permissive) | ✓ | 0 | ✓ |
| 8 | [open-mmlab/mmocr](https://github.com/open-mmlab/mmocr) | 4 739 | 781 | 82 | 🔴 Dormant | 1 | Apache-2.0 | Compatible (permissive) | — | 0 | ✓ |

---

### Vue 3 — Laboratoire offensif (solveurs / anti-détection)

| # | Dépôt | ★ | Forks | Contrib | Maintenance | Comm. 90j | Licence | Compat. proprio | SEC | Adv | CI |
|--|--|--|--|--|--|--|--|--|--|--|--|
| 1 | [sml2h3/ddddocr](https://github.com/sml2h3/ddddocr) | 14 335 | 2 296 | 6 | 🟡 Faible | 1 | MIT | Compatible (permissive) | — | 0 | — |
| 2 | [ultrafunkamsterdam/undetected-chromedriver](https://github.com/ultrafunkamsterdam/undetected-chromedriver) | 12 701 | 1 337 | 11 | 🟡 Ralenti | 1 | GPL-3.0 | Incompatible distribution propriétaire | — | 0 | ✓ |
| 3 | [NopeCHALLC/nopecha-extension](https://github.com/NopeCHALLC/nopecha-extension) | 10 414 | 180 | 4 | 🟡 Faible | 3 | MIT | Compatible (permissive) | — | 0 | — |
| 4 | [dessant/buster](https://github.com/dessant/buster) | 9 143 | 681 | 2 | 🟢 Active | 39 | GPL-3.0 | Incompatible distribution propriétaire | — | 0 | ✓ |
| 5 | [lining0806/PythonSpiderNotes](https://github.com/lining0806/PythonSpiderNotes) | 7 444 | 2 163 | 1 | 🔴 Dormant | 1 | ⚠ Aucune | À valider (licence non standard / absente) | — | 0 | — |
| 6 | [ultrafunkamsterdam/nodriver](https://github.com/ultrafunkamsterdam/nodriver) | 4 384 | 414 | 3 | 🟡 Faible | 6 | AGPL-3.0 | Risque SaaS fort (copyleft réseau) | — | 0 | ✓ |
| 7 | [kerlomz/captcha_trainer](https://github.com/kerlomz/captcha_trainer) | 3 207 | 822 | 3 | 🟡 Ralenti | 1 | Apache-2.0 | Compatible (permissive) | — | 0 | — |
| 8 | [zhaipro/easy12306](https://github.com/zhaipro/easy12306) | 2 911 | 726 | 2 | 🔴 Dormant | 1 | Artistic-2.0 | Compatible (permissive) | — | 0 | — |
| 9 | [nickliqian/cnn_captcha](https://github.com/nickliqian/cnn_captcha) | 2 879 | 785 | 6 | 🔴 Dormant | 1 | Apache-2.0 | Compatible (permissive) | — | 0 | — |
| 10 | [QIN2DIM/hcaptcha-challenger](https://github.com/QIN2DIM/hcaptcha-challenger) | 2 344 | 430 | 11 | 🟡 Faible | 1 | GPL-3.0 | Incompatible distribution propriétaire | — | 0 | ✓ |
| 11 | [sarperavci/GoogleRecaptchaBypass](https://github.com/sarperavci/GoogleRecaptchaBypass) | 1 785 | 279 | 3 | 🟡 Faible | 5 | ⚠ Aucune | À valider (licence non standard / absente) | — | 0 | — |

> **Cadre d'emploi (vue 3)** — au **POC, aucune contrainte** : ces solveurs locaux (`ddddocr`, `hcaptcha-challenger`…) et outils anti-détection sont **autorisés et disponibles** pour valider la technologie ; la résolution de challenges (reCAPTCHA, hCaptcha, Turnstile) n'est **pas une contrainte du POC**. Bonne pratique d'ingénierie recommandée (non bloquante) : exécuter en environnement isolé, sans comptes/cookies/jetons/secrets réels. Le **cadrage légal** (CGU des tiers, droit de réutilisation, responsabilité selon la juridiction) relève de la **phase pré-production** dédiée — il dépend des pays cibles et est traité là, jamais au POC.

---

### Vue 4 — Industrialisation de l'audit

| # | Dépôt | ★ | Forks | Contrib | Maintenance | Comm. 90j | Licence | Compat. proprio | SEC | Adv | CI |
|--|--|--|--|--|--|--|--|--|--|--|--|
| 1 | [microsoft/playwright](https://github.com/microsoft/playwright) | 91 406 | 5 953 | 470 | 🟢 Active | 834 | Apache-2.0 | Compatible (permissive) | ✓ | 0 | ✓ |
| 2 | [prometheus/prometheus](https://github.com/prometheus/prometheus) | 64 700 | 10 513 | 353 | 🟢 Active | 565 | Apache-2.0 | Compatible (permissive) | ✓ | 6 | ✓ |
| 3 | [grafana/k6](https://github.com/grafana/k6) | 30 862 | 1 562 | 238 | 🟢 Active | 278 | AGPL-3.0 | Risque SaaS fort (copyleft réseau) | — | 0 | ✓ |
| 4 | [GoogleChrome/lighthouse](https://github.com/GoogleChrome/lighthouse) | 30 405 | 9 724 | 361 | 🟢 Active | 80 | Apache-2.0 | Compatible (permissive) | — | 0 | ✓ |
| 5 | [zaproxy/zaproxy](https://github.com/zaproxy/zaproxy) | 15 308 | 2 580 | 236 | 🟢 Active | 71 | Apache-2.0 | Compatible (permissive) | ✓ | 0 | ✓ |
| 6 | [dequelabs/axe-core](https://github.com/dequelabs/axe-core) | 7 254 | 894 | 228 | 🟢 Active | 101 | MPL-2.0 | Compatible (permissive) | ✓ | 0 | ✓ |
| 7 | [open-telemetry/opentelemetry-collector](https://github.com/open-telemetry/opentelemetry-collector) | 7 160 | 2 116 | 409 | 🟢 Active | 244 | Apache-2.0 | Compatible (permissive) | — | 1 | ✓ |

---

## 3. Analyse de maintenance

La santé d'un projet open source en production se mesure à son activité récente, à la diversité de ses contributeurs et à la régularité de ses releases — pas à sa popularité.

**Méthode de classification** (colonne Maintenance) :
- 🟢 **Active** : ≥ 5 commits sur 30 jours, ou ≥ 50 sur 365 jours.
- 🟡 **Ralentie** : dernier commit entre 6 mois et 1 an, ou activité faible.
- 🔴 **Dormante** : dernier commit il y a plus d'un an.
- ⚫ **Archivée** : dépôt en lecture seule.

**Points de vigilance** :
- `mCaptcha/mCaptcha` : 17 contributeurs mais dernière release ancienne (tag v0.1.0) et activité ralentie — vitalité à confirmer avant production.
- `dessant/buster` : projet populaire (9k★) mais **2 contributeurs** — dépendance forte à un mainteneur.
- Les solveurs `kerlomz/captcha_trainer`, `nickliqian/cnn_captcha`, `zhaipro/easy12306` sont dormants : valeur pédagogique/historique uniquement.

---

## 4. Analyse de sécurité projet

| Critère | Couverture | Collecté |
|---|---|---|
| `SECURITY.md` (politique de divulgation) | 13/44 dépôts | ✓ API |
| Advisories GitHub publiées | 8 dépôts | ✓ API |
| Dependabot / Renovate (MAJ dépendances) | voir colonne Bot | ✓ API contents |
| CI/CD automatisée | voir colonne CI | ✓ API contents |
| **Score OpenSSF Scorecard** | **non collecté** | ✗ hôte hors allowlist |
| **CVE / dépendances transitives** | **non collecté** | ✗ nécessite SCA dédié |
| **SBOM / signatures / provenance SLSA** | **non collecté** | ✗ à vérifier par release |

Les advisories les plus nombreuses concernent les projets matures et critiques (`owasp-modsecurity/ModSecurity` : 7, `prometheus/prometheus` : 6), ce qui traduit un **processus de divulgation responsable**, pas une faiblesse.

---

## 5. Analyse juridique (soumise à validation)

| Famille de licence | Dépôts concernés | Implication pour un produit propriétaire / SaaS |
|---|---|---|
| **Permissive** (MIT, Apache-2.0, BSD, MPL-2.0, Artistic-2.0) | majorité | Intégration possible avec attribution ; MPL-2.0 impose le partage des fichiers modifiés. |
| **GPL-3.0** | `chaitin/SafeLine`, `ultrafunkamsterdam/undetected-chromedriver`, `dessant/buster`, `QIN2DIM/hcaptcha-challenger` | Incompatible avec une distribution propriétaire d'un produit lié. Usage en service interne sans distribution généralement toléré (à valider). |
| **AGPL-3.0** | `bunkerity/bunkerweb`, `mCaptcha/mCaptcha`, `ultrafunkamsterdam/nodriver`, `grafana/k6` | **Copyleft réseau** : la simple mise à disposition via le réseau déclenche l'obligation de fournir le code source. Impact direct sur un modèle SaaS. |
| **Aucune licence OSI** | `lining0806/PythonSpiderNotes`, `sarperavci/GoogleRecaptchaBypass` | Par défaut « tous droits réservés ». Tout usage au-delà de la consultation est juridiquement risqué. **Validation juridique obligatoire.** |

**Limites de cette analyse** : la compatibilité des **dépendances transitives** n'a pas été examinée (un projet MIT peut embarquer une dépendance GPL). Aucune **double licence** n'a été recherchée systématiquement. Ces deux points relèvent de la revue juridique dédiée.

---

## 6. Décision d'architecture

| Niveau | Projets |
|---|---|
| **Production prioritaire** | SafeLine, BunkerWeb, Coraza + OWASP CRS, ModSecurity, Cap, ALTCHA, Anubis |
| **Production selon contexte** | go-captcha, mosparo, invisible_captcha (Rails), Prosopo, mCaptcha (sous réserve de maintenance) |
| **Baseline d'analyse** | OpenCV, Tesseract, PaddleOCR, EasyOCR, Albumentations, Playwright |
| **Laboratoire ML isolé** | ddddocr, captcha_trainer, cnn_captcha |
| **Laboratoire offensif** (solveurs / anti-détection ; isolé recommandé) | undetected-chromedriver, nodriver, NopeCHA, Buster, hcaptcha-challenger, GoogleRecaptchaBypass |
| **À écarter d'un nouveau projet** | laravel-auth (démo applicative), easy12306 (solveur dormant, licence atypique), dépôts dormants |

> Chaque choix « production » reste conditionné à : (1) validation juridique de la licence, (2) collecte du score OpenSSF Scorecard, (3) exécution du benchmark du §9.

---

## 7. Schéma attendu — chaîne d'audit en laboratoire

```
                    Navigateur de test
                          |
              Playwright / Selenium contrôlé
                          |
            +-------------+-------------+
            |                           |
            v                           v
    Capture image / audio          Traces HTTP
            |                           |
            v                           v
         OpenCV                 ZAP / proxy d'audit
            |
            +--> Tesseract
            +--> EasyOCR
            +--> PaddleOCR
            +--> ddddocr
            +--> modèle interne (captcha_trainer / CNN)
            |
            v
              Calcul des métriques (§9)
            |
            v
   Prometheus / OpenTelemetry / Grafana
```

---

## 8. Modèle du tableau maître (30 colonnes)

Le fichier `captcha-audit-master.csv` porte 30 colonnes, dont deux colonnes de **preuve** : **`preuve_licence`** (lien direct vers le fichier LICENSE du dépôt) et **`preuve_activite`** (timestamp `pushed_at` retourné par l'API). Les autres colonnes : Dépôt, Catégorie, Étoiles, Forks, Contributeurs, Mainteneur unique, Issues ouvertes, PR ouvertes, Commits 30/90/365j, Jours depuis dernier commit, Maintenance, Nb releases, Dernière release, Jours depuis release, Releases/an, Archivé, Licence, Compat. propriétaire, SECURITY.md, Advisories, Dependabot, Renovate, CI/CD, Santé %, Langage, URL projet.

---

## 9. Grille de benchmark — à exécuter en laboratoire

Aucun banc comparatif standardisé public n'existe pour ces outils. Les indicateurs ci-dessous doivent être **mesurés** sur un corpus possédé. Les repères issus de la littérature sont donnés à titre indicatif et **non vérifiés** dans ce contexte.

| Indicateur | Unité | Repère public (non vérifié) | Méthode de mesure |
|---|---|---|---|
| Taux de résolution OCR/ML | % | Cassage 7–100 % selon le schéma (littérature) ; modèles attention récents ~95–97 % sur jeux spécifiques | N essais sur corpus étiqueté |
| Taux de résolution humaine | % | — | Panel d'utilisateurs |
| Exact Match | % | — | Comparaison stricte |
| CER / WER | valeur | — | Distance d'édition normalisée |
| Latence P50 / P95 / P99 | ms | — | Histogramme sur N requêtes |
| Consommation CPU / RAM | unités | — | Métrologie conteneur |
| Coût par million de challenges | € | — | Coût infra + service externe |
| Faux positifs anti-bot | % | — | Trafic légitime testé |
| Faux négatifs | % | — | Trafic bot testé |
| Taux d'abandon utilisateur | % | — | Analytics du parcours |
| Résistance au rejeu | succès/échec | — | Rejeu de jeton capturé |
| Conformité WCAG | A/AA/AAA | — | axe-core + audit manuel |

---

## 10. Méthodologie et limites

- **Données API** : collectées via l'API REST GitHub v3 authentifiée à 2026-06-22T18:55:53Z. Le nombre de contributeurs est dérivé de l'en-tête `Link` (pagination) et reflète les contributeurs avec commits attribués. Les compteurs `Commits 30/90/365j` sont obtenus par pagination sur l'endpoint commits avec filtre `since`.
- **Issues vs PR** : séparées via l'API Search (les « open issues » de l'API repos incluent les PR).
- **SECURITY.md** : détecté via l'API `contents` (racine, `.github/`, `docs/`) — plus fiable que `community/profile`, qui s'est révélé incomplet lors du relevé.
- **Licences** : valeur SPDX de l'API, complétée par lecture directe du fichier `LICENSE` pour les cas où l'API renvoie `NOASSERTION` (licence présente mais non reconnue au format standard) — c'est le cas de `tiagozip/cap` et `mojocn/base64Captcha` (Apache-2.0 confirmé par lecture du fichier).
- **Non collecté dans ce contexte** : score OpenSSF Scorecard (`api.securityscorecards.dev` hors allowlist réseau du conteneur), CVE et dépendances transitives (nécessitent un outil SCA dédié), SBOM / signatures Cosign / provenance SLSA (à vérifier par release).
- **Pour rafraîchir** : interroger l'endpoint repos de l'API avec un jeton authentifié (5 000 req/h). Pour le Scorecard, ajouter `api.securityscorecards.dev` à l'allowlist ou exécuter l'outil `scorecard` en local sur chaque dépôt.
- **Reproductibilité** : le JSON brut joint contient l'intégralité des champs collectés avec horodatage et empreinte SHA-256, permettant de rejouer ou d'auditer le relevé.
