"""Package acquisitionv1 — types du contrat d'acquisition (équivalent Python).

Ces types sont l'équivalent Python des messages Protobuf de
``contracts/proto/*.proto`` (package ``acquisition.v1``). Ils sont normalement
générés par ``buf generate`` ; comme buf/protoc ne sont pas disponibles dans cet
environnement, ils sont écrits à la main en restant fidèles aux ``.proto`` (mêmes
champs, mêmes valeurs d'enum, noms de champs JSON en ``snake_case`` identiques au
proto3 JSON mapping) ET à la tranche Go de référence
(``contracts/gen/go/acquisitionv1``).

ZÉRO dépendance Temporal : ce paquet est le vocabulaire partagé et ne connaît pas
l'orchestrateur. Les enums se sérialisent sous leur forme NOMINALE (``"STATIC"``,
``"SUCCESS"``, ``"RAW_RESPONSE"``…), comme côté Go (proto3 JSON mapping).
"""

from .enums import AcquisitionMode, ArtifactKind, FinalState
from .command import AcquisitionCommand
from .http_exchange import HttpExchange
from .artifact import Artifact
from .result import AcquisitionResult

__all__ = [
    "AcquisitionMode",
    "FinalState",
    "ArtifactKind",
    "AcquisitionCommand",
    "HttpExchange",
    "Artifact",
    "AcquisitionResult",
]
