"""Échange HTTP brut capturé (http_exchange.proto / http_exchange.go)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class HttpExchange(BaseModel):
    """Échange HTTP brut capturé (requête + réponse complètes).

    Capacité transverse du module (cf. docs/architecture/06-validation-artefacts.md).
    Mêmes champs / mêmes noms JSON snake_case que la tranche Go. Les champs vides
    sont omis à la sérialisation (parité ``omitempty``) via ``exclude_none`` /
    ``exclude_defaults`` côté appelant.
    """

    model_config = ConfigDict(extra="forbid")

    method: str = ""
    url: str = ""
    final_url: str = ""  # après redirections
    status: int = 0
    request_headers: dict[str, str] = Field(default_factory=dict)
    response_headers: dict[str, str] = Field(default_factory=dict)
    timings: dict[str, float] = Field(default_factory=dict)  # dns/tls/ttfb/total (ms)
    protocol: str = ""  # HTTP/1.1, HTTP/2, HTTP/3


__all__ = ["HttpExchange"]
