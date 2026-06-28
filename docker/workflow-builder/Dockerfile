# Workflow Builder (Synergy Codes — Apache-2.0) : éditeur visuel d'authoring de workflows
# (apps/demo = canvas React Flow). OUTIL DE TEST opt-in, monté dans le compose via le profil
# "builder". Frontend PUR : aucune dépendance Temporal/backend (vérifié) → servi en statique.
#
# Pourquoi un Dockerfile maison plutôt que apps/demo/Dockerfile (amont) : ce dernier est
# « deploy-only » (FROM nginx + COPY ./dist/apps/demo déjà buildé) et référence des confs
# nginx (tools/deployment/nginx/*) ABSENTES du dépôt (injectées par leur CI). On construit
# donc tout nous-mêmes, de façon autonome et reproductible.
#
# Le SOURCE est cloné ICI (pas de submodule, pas de vendoring), épinglé sur un tag stable.
# Contexte de build minimal (ce dossier) : le Dockerfile n'a besoin que de default.conf.
#
#   docker compose --profile builder up -d --build workflow-builder   → http://localhost:4202

# ---------- Stage 1 : build du demo (Vite) ----------
FROM node:22.12.0-bookworm-slim AS builder

# Tag amont à construire (dernière version stable) et dépôt source.
ARG WB_REF=v2.1.0
ARG WB_REPO=https://github.com/synergycodes/workflowbuilder.git

# Pas de hooks git (husky) ni de télémétrie pendant l'install CI.
ENV HUSKY=0 \
    CI=true \
    DO_NOT_TRACK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# pnpm épinglé (= packageManager du repo amont), installé via npm et NON corepack :
# le corepack fourni par node:22.12.0 a des clés de signature périmées et échoue à vérifier
# le paquet pnpm ("Cannot find matching keyid"). npm i -g est déterministe et sans ce souci.
RUN npm install -g pnpm@10.17.0

WORKDIR /src
RUN git clone --depth 1 --branch "${WB_REF}" "${WB_REPO}" .

# Install figée (pnpm-lock.yaml) sur tout le workspace, puis build du seul app demo.
# vite résout le SDK workspace depuis les sources → pas de pré-build de lib nécessaire.
# Sortie : /src/dist/apps/demo (cf. apps/demo/vite.config.mts : outDir ../../dist/apps/demo).
RUN pnpm install --frozen-lockfile
RUN pnpm --filter @workflow-builder/demo build

# ---------- Stage 2 : service statique (nginx) ----------
FROM nginx:mainline-alpine AS runtime

# Conf SPA maison (l'amont ne la versionne pas).
COPY default.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /src/dist/apps/demo /usr/share/nginx/html

EXPOSE 80
# nginx:alpine fournit déjà le CMD/ENTRYPOINT (nginx -g 'daemon off;').
