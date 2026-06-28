"""Résultat d'acquisition — sortie du système (result.proto / result.go)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from .artifact import Artifact
from .enums import AcquisitionMode, FinalState
from .http_exchange import HttpExchange


class AcquisitionResult(BaseModel):
    """Sortie du système (result.proto).

    ``observed_at`` correspond à ``google.protobuf.Timestamp`` dans le ``.proto`` ;
    ici un ``datetime`` (UTC), sérialisé en RFC3339 avec suffixe ``Z`` — équivalent
    du proto3 JSON mapping d'un Timestamp et de la tranche Go (``time.Time`` UTC).

    Parité ``omitempty`` (Go) : ``acquisition_id``, ``final_state`` et
    ``observed_at`` sont toujours présents ; ``mode``, ``artifacts``,
    ``http_exchange`` et ``error`` sont omis quand vides — obtenu en sérialisant
    avec ``exclude_defaults=True`` tout en gardant les trois champs requis via
    ``model_dump_json`` côté appelant (cf. storage.py / acquire.py).
    """

    model_config = ConfigDict(extra="forbid")

    acquisition_id: str
    final_state: FinalState
    mode: AcquisitionMode = AcquisitionMode.ACQUISITION_MODE_UNSPECIFIED
    artifacts: list[Artifact] = Field(default_factory=list)
    http_exchange: HttpExchange | None = None
    observed_at: datetime
    error: str = ""

    @field_serializer("observed_at")
    def _serialize_observed_at(self, value: datetime) -> str:
        """RFC3339 UTC avec ``Z`` (parité proto3 JSON Timestamp / Go time.Time)."""
        # isoformat() rend "+00:00" pour un datetime aware UTC ; on normalise en "Z".
        text = value.isoformat()
        if text.endswith("+00:00"):
            text = text[: -len("+00:00")] + "Z"
        return text


__all__ = ["AcquisitionResult"]
