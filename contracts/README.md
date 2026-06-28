# contracts/ — vocabulaire partagé (Protobuf)

**Source unique** des contrats entre tous les langages. **Zéro dépendance Temporal.**

- `proto/` — définitions `.proto` (à éditer) : `command`, `result`, `artifact`, `http_exchange`.
- `gen/{go,ts,python,java}/` — types **générés** par `buf generate` (**ne pas éditer à la main**).

```bash
cd contracts && buf generate    # régénère gen/ pour les 4 langages
```

Règle de dépendance (cf. [`../docs/structure-projet.md`](../docs/structure-projet.md)) : `core/`, `platform/` et
`orchestration/` importent les types **générés** ; aucun code métier ne dépend de Temporal.
