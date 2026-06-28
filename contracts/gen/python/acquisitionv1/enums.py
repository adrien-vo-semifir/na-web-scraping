"""Enums du contrat d'acquisition (enums.go / *.proto).

Chaque enum est une ``str``-enum dont la VALEUR est le nom nominal proto3
(``"STATIC"``, ``"SUCCESS"``, ``"RAW_RESPONSE"``…). Ainsi, sérialisés par pydantic
ou ``json``, ils produisent exactement la même chaîne que la tranche Go (proto3
JSON mapping : ``MarshalJSON`` renvoie le nom).
"""

from __future__ import annotations

from enum import Enum


class AcquisitionMode(str, Enum):
    """Mode d'acquisition d'une ressource (command.proto)."""

    ACQUISITION_MODE_UNSPECIFIED = "ACQUISITION_MODE_UNSPECIFIED"
    STATIC = "STATIC"  # HTTP statique (transport)
    BROWSER = "BROWSER"  # rendu navigateur
    FILE = "FILE"  # téléchargement de fichier

    def __str__(self) -> str:  # parité avec fmt.Stringer côté Go
        return self.value


class FinalState(str, Enum):
    """État final normalisé d'une acquisition (result.proto)."""

    FINAL_STATE_UNSPECIFIED = "FINAL_STATE_UNSPECIFIED"
    SUCCESS = "SUCCESS"
    UNCHANGED = "UNCHANGED"  # 304 / contenu identique
    RETRYABLE = "RETRYABLE"  # échec transitoire
    PERMANENT = "PERMANENT"  # échec définitif
    BLOCKED = "BLOCKED"  # protection / WAF / challenge

    def __str__(self) -> str:
        return self.value


class ArtifactKind(str, Enum):
    """Nature d'un artefact brut produit par un moteur (artifact.proto)."""

    ARTIFACT_KIND_UNSPECIFIED = "ARTIFACT_KIND_UNSPECIFIED"
    RAW_RESPONSE = "RAW_RESPONSE"  # réponse HTTP brute
    RENDERED_DOCUMENT = "RENDERED_DOCUMENT"  # document rendu (DOM après JS)
    PAGE_SNAPSHOT = "PAGE_SNAPSHOT"  # capture (snapshot / screenshot)
    DOWNLOADED_FILE = "DOWNLOADED_FILE"  # fichier téléchargé
    HTTP_EXCHANGE = "HTTP_EXCHANGE"  # échange HTTP sérialisé

    def __str__(self) -> str:
        return self.value


__all__ = ["AcquisitionMode", "FinalState", "ArtifactKind"]
