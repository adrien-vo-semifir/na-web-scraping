# Worker Windmill spécialisé « browser » = rang N3 de la cascade (rendu JS / SPA via Playwright).
#
# Pattern officiel Windmill (worker group "reports" + tag "chromium"), mais réalisé par IMAGE
# CUSTOM plutôt que par init-script : la config d'init-script via l'UI est Enterprise ; l'image
# pré-installe chromium et reste fiable en Community Edition.
#
# Chromium SYSTÈME (/usr/bin/chromium) piloté par Playwright via executable_path → aucun
# téléchargement de navigateur Playwright, donc pas de problème d'alignement de version.
ARG WINDMILL_VERSION=1.742.0
FROM ghcr.io/windmill-labs/windmill:${WINDMILL_VERSION}

USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      chromium fonts-liberation ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Chemin attendu par nos scripts Playwright (cf. flow acquisition, rang browser).
ENV CHROMIUM_PATH=/usr/bin/chromium
# (ENTRYPOINT / CMD hérités de l'image Windmill : le worker démarre normalement.)
