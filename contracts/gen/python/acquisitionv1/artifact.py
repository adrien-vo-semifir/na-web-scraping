"""Métadonnées d'un artefact du store objet (artifact.proto / artifact.go)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .enums import ArtifactKind


class Artifact(BaseModel):
    """Métadonnées d'un artefact déposé dans le store objet (S3 / Ceph RGW).

    Mêmes champs / noms JSON que la tranche Go. ``key`` suit la convention de lac :
    ``raw/<source>/<dataset>/<run_date>/<acquisition_id>/<name>``.
    """

    model_config = ConfigDict(extra="forbid")

    kind: ArtifactKind = ArtifactKind.ARTIFACT_KIND_UNSPECIFIED
    content_type: str = ""
    size: int = 0
    sha256: str = ""  # empreinte de contenu (dédup / intégrité)
    key: str = ""  # raw/<source>/<dataset>/<run_date>/<acquisition_id>/<name>
    uri: str = ""  # s3://bucket/key (optionnel)


__all__ = ["Artifact"]
