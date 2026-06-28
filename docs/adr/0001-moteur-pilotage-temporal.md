# ADR module 0001 — Moteur de pilotage / distribution / reprise = Temporal

- **Statut** : Accepté — 2026-06-28
- **Périmètre** : module `web-scraping` (groupes **A** pilotage, **B** orchestration distribuée, **H** persistance/reprise du blueprint [`00-hub.md`](../00-hub.md))
- **Liens** : [`08-stack-techno.md`](../08-stack-techno.md) (feuille `comparatifs`, référentiel monorepo), [`01-contrats-modele-donnees.md`](../01-contrats-modele-donnees.md), [`02-pilotage-distribution.md`](../02-pilotage-distribution.md), [`07-…`](../07-persistance-securite-exploitation.md) ; monorepo : ADR 0013 (Dagster = plan de contrôle), ADR 0021 (module = submodule).

## Contexte

Le cœur du module (groupes A/B/H) demande : file à baux + DLQ, garanties (au-moins-une-fois + **idempotence**),
machine d'état (fichier 01), et surtout **reprise sans perte d'état** de navigations longues (checkpoints,
`frontier_state`). Une comparaison approfondie de 5 moteurs (Temporal, Hatchet, Bento, Apache Camel, Celery) a été
menée (feuille `comparatifs`, référentiel monorepo).

**Principe directeur appliqué** (repo-wide, cf. CLAUDE.md) : **le POC est une base destinée à la PRODUCTION** et
doit être au plus proche du final → on valorise les qualités de **production** (durabilité, idempotence, reprise,
maturité). Le **langage** et le **poids / single-node au POC** ne sont **pas** des critères.

## Décision

Le **moteur de pilotage / distribution / reprise interne** du module est **Temporal** (durable execution).

- Les **workers** (Playwright / httpx / parsing) sont des **activités** Temporal en **Python** (SDK natif).
- La **reprise (groupe H)** est **event-sourced** : l'historique du workflow EST le checkpoint → `frontier_state` /
  `serializable_state` / `visited_resources` quasi **implicites** ; **idempotence** (activity-id sur
  `acquisition_id + configuration_version`) et **réconciliation** (heartbeat) **natives**.
- **Persistance sur PostgreSQL** (réutilise la base du module). **Valkey** reste **cache / sessions partagées**,
  **plus broker** (Temporal a sa propre file). **Celery est retiré** du module.
- **Discipline** : Temporal est **strictement intra-module**. Le **plan de contrôle global reste Dagster**
  ([ADR 0013](../../../docs/adr/0013-orchestration-plan-controle-unique.md)) qui **déclenche** le module (gRPC/REST) ;
  on **n'utilise pas** les Schedules/Cron de Temporal comme 2ᵉ ordonnanceur. Toute **I/O** (réseau, horloge,
  random) passe par une **activité** (déterminisme du corps de workflow).

## Pourquoi

- **Prod-close** : durable execution + idempotence + reprise sont les qualités **de production** dont le module a
  besoin — Temporal les fournit nativement, au lieu de les **coder à la main** (ce que Celery imposerait).
- **Alignement contrats** : la FSM « as code » et les états du fichier 01 se modélisent directement.
- **Maturité / pérennité** maximales (référence du domaine), licence **MIT**, SDK Python natif.

## Conséquences

➕ Groupe H (reprise/checkpoints) **quasi gratuit** ; idempotence/réconciliation natives ; FSM as-code.
➕ Workers Playwright/httpx intacts (activités Python) ; déclenchement par Dagster inchangé.
➖ **Temporal = service à opérer** (serveur + DB) — assumé (POC = base prod, le poids n'est pas un critère).
➖ **Celery retiré** ; **Valkey** rétrogradé en cache/sessions ; `08-stack` / `etapes` mis à jour.
➖ Côté monorepo, « Celery = executor scraping » ([ADR 0013](../../../docs/adr/0013-orchestration-plan-controle-unique.md))
  est **superseded pour le module** (à réaligner dans 0013).

## Alternatives écartées

- **Celery** : mature/léger mais **pas de reprise durable** (groupe H) ; idempotence/DLQ/FSM à coder → **pas prod-close**.
- **Hatchet** : durable + MIT + Postgres-only, mais **SDK v1 pre-release/alpha** = risque pour un système destiné à
  la prod (à reconsidérer une fois v1 stabilisée).
- **Apache Camel** : routeur EIP excellent mais **pas de workflow durable/reprise** → au mieux routeur en périphérie.
- **Bento** : pipeline ETL stateless, **pas un orchestrateur** (groupes B/H hors modèle).

## Réversibilité

Le **contrat du fichier 01** (`AcquisitionCommand` / `AcquisitionResult` / `Artifact` / `HttpExchange` /
`Checkpoint`) reste la **frontière stable** : on peut changer de moteur **sans toucher** les workers Playwright/httpx
ni l'aval. Pas de lock-in.
