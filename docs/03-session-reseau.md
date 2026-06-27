# 03 — Session et réseau

> **Groupe** : C (session et réseau).
> **Prérequis** : `00-hub.md`, `01-contrats-modele-donnees.md`.
> **Contenu** : gestion de session, contrôle d'accès, couche réseau, contrôle des sorties et anti-SSRF, adaptation contrôlée du contexte.

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

La couche réseau est commune aux trois moteurs (HTTP, rendu, fichier). Le contrôle des adresses résolues s'intercale entre la résolution DNS et l'établissement de connexion : c'est le point anti-SSRF.

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

## 4. Contrôle des sorties et anti-SSRF

Point de sécurité critique. Le contrôle des adresses résolues précède toute connexion et est rejoué après chaque redirection.

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
S -> T : ré-authentifier (mécanisme autorisé)
T --> S : nouvelle session
S --> W : contexte renouvelé
W -> N : rejouer la requête
N -> T : émettre
T --> N : 200
N --> W : contenu
@enduml
```

Le renouvellement de session est un mécanisme autorisé : il rejoue l'authentification normale de la source. Il ne s'agit pas de contourner une protection mais de rétablir un accès légitime expiré.

---

## 6. Adaptation contrôlée du contexte

Remplace toute notion de « stealth ». Distingue la compatibilité technique légitime de la dissimulation. Seule la première est admise, et uniquement si la politique l'autorise.

```mermaid
flowchart LR
    SIGNAL[Incompatibilité détectée] --> POLICY{Adaptation autorisée ?}
    POLICY -- Oui --> CONTEXT[Adapter le contexte d'acquisition]
    POLICY -- Non --> STOP[Arrêter ou demander une revue]
    CONTEXT --> SESSION[Cohérence de session]
    CONTEXT --> CLIENT[Compatibilité du client]
    CONTEXT --> NETWORK[Chemin réseau autorisé]
    CONTEXT --> RATE[Rythme d'accès]
    CONTEXT --> RENDER[Mode de rendu]
    SESSION --> RETRY[Nouvelle tentative]
    CLIENT --> RETRY
    NETWORK --> RETRY
    RATE --> RETRY
    RENDER --> RETRY
```

| Admis (compatibilité) | Exclu — voir encart hub § 6 |
| --- | --- |
| Maintien de la cohérence de session | Rotation automatique d'identité pour éviter un blocage |
| Compatibilité du client avec les exigences normales du site | Usurpation d'empreinte pour déjouer une détection |
| Utilisation d'un chemin réseau autorisé | Rotation de proxies destinée à contourner un bannissement |
| Ajustement du rythme d'accès | — |
| Choix du mode de rendu adapté | — |

> Rappel verrouillé (hub § 6) : la rotation automatique d'identité ou de réseau n'est pas le comportement standard de la plateforme.
