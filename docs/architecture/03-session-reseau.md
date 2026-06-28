# 03 — Session et réseau

> **Groupe** : C (session et réseau).
> **Prérequis** : `00-hub.md`, `01-contrats-modele-donnees.md`.
> **Contenu** : gestion de session, contrôle d'accès, couche réseau, contrôle des sorties et anti-SSRF (différé pré-production), adaptation du contexte.
> **Stack** : client HTTP **httpx** (sync+async, HTTP/2, pool, timeouts, en-têtes conditionnels ETag/304, streaming) ; transport furtif **curl_cffi** (TLS/JA3, escalade N2) ; cache conditionnel **Hishel** ; sniffing MIME **filetype** ; détection charset **charset-normalizer**. Détail : `08-stack-techno.md`.
>
> 🔒 **POC sans contrainte.** Le contrôle des sorties / anti-SSRF / DNS pinné (§ 4) est documenté comme **architecture cible** mais relève de la **phase pré-production** : **aucun blocage actif au POC**. Voir l'encart du hub (`00-hub.md`).

---

## 1. Diagramme de composants

```plantuml
@startuml
skinparam componentStyle rectangle
skinparam shadowing false
skinparam defaultFontName "sans"

package "Accès et session (C)" {
  [Politique par source] as POL
  [Limitation de fréquence] as RATE
  [Limitation de concurrence] as CONC
  [Gestionnaire de sessions] as SESSION
  [Authentification] as AUTH
  [Gestion des en-têtes] as HEAD
  [Gestion des cookies] as COOKIE
}

package "Réseau (C)" {
  [Choix du chemin réseau] as ROUTING
  [Résolution DNS] as DNS
  [Contrôle des adresses résolues] as IPCHK
  [Gestion TLS] as TLS
  [Pool de connexions] as POOL
  [Gestion des délais] as TIMEOUT
  [Contrôle des sorties] as EGRESS
}

database "Secrets" as VAULT
[Moteurs] as ENGINE
[Cible externe] as TARGET

ENGINE --> POL
POL --> RATE
RATE --> CONC
CONC --> SESSION
VAULT --> AUTH
AUTH --> SESSION
SESSION --> HEAD
HEAD --> COOKIE
COOKIE --> ROUTING
ROUTING --> DNS
DNS --> IPCHK
IPCHK --> TLS
TLS --> POOL
POOL --> TIMEOUT
TIMEOUT --> EGRESS
EGRESS --> TARGET
@enduml
```

La couche réseau est commune aux trois moteurs (HTTP, rendu, fichier). Côté client HTTP, elle s'appuie sur **httpx** (pool de connexions, HTTP/2, délais de connexion/lecture, en-têtes conditionnels) ; le transport furtif **curl_cffi** (empreinte TLS/JA3) est mobilisé en escalade. Le contrôle des adresses résolues s'intercalerait entre la résolution DNS et l'établissement de connexion (point anti-SSRF) — **prévu mais inactif au POC**, voir § 4.

---

## 2. Diagramme d'activité — chaîne d'accès

```mermaid
flowchart TB
    CMD[Commande] --> POL[Application de la politique de source]
    POL --> RATE{Quota et fréquence}
    RATE -- Dépassé --> WAIT[Temporisation]
    WAIT --> RATE
    RATE -- OK --> CONC{Concurrence disponible}
    CONC -- Saturée --> WAIT
    CONC -- OK --> SESSION[Création ou restauration de session]
    SESSION --> AUTH[Authentification si requise]
    AUTH --> HEAD[Composition des en-têtes]
    HEAD --> COOKIE[Application des cookies]
    COOKIE --> NET[Remise à la couche réseau]
```

La session porte cookies, jetons temporaires, jetons de formulaire et état de navigation. Les secrets d'authentification sont résolus depuis le coffre, jamais codés en dur ni journalisés en clair.

---

## 3. Couche réseau détaillée

Fonctions couvertes : résolution DNS, contrôle des adresses résolues, gestion TLS et certificats, protocoles et versions, pools de connexions, keep-alive, délais de connexion/lecture/traitement, redirections, compression, limites de réponse, chemins réseau autorisés, politique de sortie, corrélation des erreurs réseau, gestion IPv4/IPv6.

```mermaid
flowchart LR
    URL[Adresse cible] --> NORM[Normalisation et canonicalisation]
    NORM --> DNS[Résolution DNS]
    DNS --> RESOLVED[Adresses résolues IPv4 / IPv6]
    RESOLVED --> TLS[Négociation TLS et vérification du certificat]
    TLS --> POOL[Acquisition d'une connexion du pool]
    POOL --> SENDTIME[Application des délais]
    SENDTIME --> SEND[Émission de la requête]
```

Chaque échange alimente le contrat `HttpExchange` (fichier 01) : timings DNS/connect/TLS/TTFB, version de protocole, adresse résolue, réutilisation de connexion.

---

## 4. Contrôle des sorties et anti-SSRF *(architecture cible — phase pré-production)*

> 🔒 **Différé pré-production — inactif au POC.** Au POC le module **collecte librement**, sans allowlist de domaines, sans blocage d'adresses ni politique d'egress. La cible décrite ci-dessous (contrôle des adresses résolues précédant toute connexion, rejoué après chaque redirection, DNS pinné) est **à coder en phase pré-production** — elle dépend des pays visés. Aucun outil dédié n'est encore « Sélectionné » (cf. `08-stack-techno.md`, `etapes.md`). Le diagramme et le tableau ci-après documentent ce mécanisme **futur**, pas un contrôle appliqué au POC.

```mermaid
flowchart TB
    TARGET[Adresse à atteindre] --> PARSE[Analyser et normaliser]
    PARSE --> DOMAIN{Domaine autorisé ?}
    DOMAIN -- Non --> REJECT([Refuser])
    DOMAIN -- Oui --> DNS[Résoudre l'adresse]
    DNS --> IPCHK{Adresse autorisée ?}
    IPCHK -- Privée, locale,<br>métadonnées cloud --> REJECT
    IPCHK -- Publique autorisée --> CONNECT[Établir la connexion]
    CONNECT --> REQ[Émettre la requête]
    REQ --> REDIR{Redirection ?}
    REDIR -- Oui --> PARSE
    REDIR -- Non --> RESP[Recevoir la réponse]
```

| Risque réseau | Contrôle |
| --- | --- |
| SSRF | Liste de domaines et réseaux autorisés |
| Accès aux réseaux internes | Blocage des adresses privées, locales et métadonnées cloud |
| Redirection malveillante | Revalidation complète après chaque redirection |
| DNS rebinding | Validation de l'adresse résolue immédiatement avant connexion |
| Exfiltration réseau | Contrôle des destinations sortantes (politique d'egress) |

La quarantaine de contenu (bombe zip, réponse infinie) et l'isolation du navigateur sont traitées dans le fichier 07 (sécurité d'exécution).

---

## 5. Diagramme de séquence — session expirée en cours d'acquisition

```plantuml
@startuml
skinparam shadowing false
skinparam defaultFontName "sans"
participant "Worker" as W
participant "Session" as S
database "Secrets" as V
participant "Réseau" as N
participant "Cible" as T

W -> S : restaurer session
S --> W : contexte (cookies, jetons)
W -> N : requête
N -> T : émettre
T --> N : 401 / session expirée
N --> W : réponse d'authentification requise
W -> S : renouveler la session
S -> V : résoudre les secrets
V --> S : identifiants
S -> T : ré-authentifier
T --> S : nouvelle session
S --> W : contexte renouvelé
W -> N : rejouer la requête
N -> T : émettre
T --> N : 200
N --> W : contenu
@enduml
```

Le renouvellement de session rejoue l'authentification de la source pour rétablir un accès expiré.

---

## 6. Adaptation du contexte

Leviers d'adaptation du contexte d'acquisition disponibles lorsqu'une incompatibilité est détectée.

```mermaid
flowchart LR
    SIGNAL[Incompatibilité détectée] --> CONTEXT[Adapter le contexte d'acquisition]
    CONTEXT --> SESSION[Cohérence de session]
    CONTEXT --> CLIENT[Compatibilité du client]
    CONTEXT --> NETWORK[Chemin réseau]
    CONTEXT --> RATE[Rythme d'accès]
    CONTEXT --> RENDER[Mode de rendu]
    SESSION --> RETRY[Nouvelle tentative]
    CLIENT --> RETRY
    NETWORK --> RETRY
    RATE --> RETRY
    RENDER --> RETRY
```

| Levier d'adaptation |
| --- |
| Maintien de la cohérence de session |
| Compatibilité du client avec les exigences du site |
| Rotation d'identité ou de proxies |
| Usurpation d'empreinte |
| Ajustement du rythme d'accès |
| Choix du mode de rendu adapté |
