# Worker Go — porte les Workflows (orchestration/temporal/workflows-go) + Activities Go éventuelles.
# Contexte de build = RACINE du repo (cf. docs/structure-projet.md §6) :
#   docker build -f docker/workflow-worker/Dockerfile -t workflow-worker .
FROM golang:1.23 AS build
WORKDIR /src
# Contrats générés + couche d'orchestration Go (et core Go si présent)
COPY contracts/gen/go ./contracts/gen/go
COPY orchestration/temporal/workflows-go ./orchestration/temporal/workflows-go
COPY orchestration/temporal/worker-bootstrap ./orchestration/temporal/worker-bootstrap
WORKDIR /src/orchestration/temporal/worker-bootstrap
# --- À activer quand le code Go existe (go.mod + main) : ---
# RUN go build -o /out/workflow-worker .
# FROM gcr.io/distroless/base-debian12
# COPY --from=build /out/workflow-worker /workflow-worker
# ENTRYPOINT ["/workflow-worker"]
CMD ["sh", "-c", "echo '[workflow-worker] code Go à implémenter (orchestration/temporal/workflows-go + worker-bootstrap)'; sleep infinity"]
