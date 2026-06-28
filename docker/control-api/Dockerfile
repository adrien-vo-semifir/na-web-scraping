# platform/control-api — point d'entrée REST des commandes d'acquisition.
# Langage à confirmer (Go pressenti). Contexte de build = RACINE du repo.
#   docker build -f docker/control-api/Dockerfile -t control-api .
FROM golang:1.23 AS build
WORKDIR /src
COPY contracts/gen/go ./contracts/gen/go
COPY platform/control-api ./platform/control-api
WORKDIR /src/platform/control-api
# RUN go build -o /out/control-api .
# FROM gcr.io/distroless/base-debian12
# COPY --from=build /out/control-api /control-api
# ENTRYPOINT ["/control-api"]
EXPOSE 8000
CMD ["sh", "-c", "echo '[control-api] code à implémenter (platform/control-api)'; sleep infinity"]
