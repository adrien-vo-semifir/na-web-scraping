"""Commande d'acquisition — entrée du système (command.proto / command.go)."""

from __future__ import annotations

import hashlib

from pydantic import BaseModel, ConfigDict, Field

from .enums import AcquisitionMode


class AcquisitionCommand(BaseModel):
    """Entrée du système (command.proto).

    ``acquisition_id`` n'est PAS un champ du message : il est dérivé
    (``url`` + ``configuration_version``) côté code via :meth:`acquisition_id`,
    pour garantir l'idempotence — strictement comme la tranche Go.
    """

    model_config = ConfigDict(extra="forbid")

    url: str
    source: str = ""  # identifiant logique de la source (optionnel)
    dataset: str = ""  # jeu de données cible (optionnel)
    mode: AcquisitionMode = AcquisitionMode.ACQUISITION_MODE_UNSPECIFIED
    configuration_version: str = ""  # version de configuration (idempotence)
    headers: dict[str, str] = Field(default_factory=dict)  # en-têtes additionnels

    def acquisition_id(self) -> str:
        """Identifiant idempotent : ``sha256(url + "|" + configuration_version)[:16]``.

        Deux commandes ayant la même URL et la même version de configuration
        produisent le même ``acquisition_id`` (idempotence), et donc la même clé
        objet en stockage. Identique à ``(*AcquisitionCommand).AcquisitionId`` (Go).
        """
        digest = hashlib.sha256(
            (self.url + "|" + self.configuration_version).encode("utf-8")
        ).hexdigest()
        return digest[:16]


__all__ = ["AcquisitionCommand"]
