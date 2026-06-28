"""Écriture du brut — équivalent Python de platform/storage (local.go + store.go).

Artefacts (réponse HTTP, échange HTTP sérialisé) + manifest JSON décrivant
l'acquisition (= AcquisitionResult). Infrastructure métier — N'IMPORTE JAMAIS le
SDK Temporal. Un seul sink ici : ``LocalSink`` (disque, dev) ; le store S3 (Ceph
RGW) viendra à l'implémentation, derrière la même frontière ``Sink``.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from acquisitionv1 import (
    AcquisitionCommand,
    AcquisitionResult,
    Artifact,
    ArtifactKind,
    FinalState,
)

from .fetcher import FetchResult
from .shared import object_key, sha256_hex

# Noms d'objets standard d'une acquisition (parité 1:1 avec store.go).
NAME_RESPONSE = "response.bin"  # corps brut de la réponse HTTP (RAW_RESPONSE)
NAME_HTTP_EXCHANGE = "http_exchange.json"  # échange HTTP sérialisé (HTTP_EXCHANGE)
NAME_MANIFEST = "manifest.json"  # manifest JSON (= AcquisitionResult)

# Racine locale par défaut si DATA_DIR n'est pas défini (parité DefaultDataDir).
DEFAULT_DATA_DIR = "./data"


class Sink(Protocol):
    """Frontière d'écriture du brut : magasin d'objets adressés par clé.

    ``write`` dépose ``data`` sous ``key`` (convention de lac : voir object_key),
    avec son type MIME et des métadonnées libres, et renvoie l'URI absolue écrite
    (``file://…`` en local, ``s3://bucket/key`` sur S3). Identique à l'interface Go.
    """

    def write(
        self, key: str, data: bytes, content_type: str, meta: dict[str, str]
    ) -> str: ...


@dataclass
class LocalSink:
    """Écrit les objets sous une racine du FS, en reproduisant la clé en dossiers.

    Sink de développement : ``raw/web/pages/<date>/<id>/response.bin`` devient un
    fichier du même chemin relatif sous ``root``. Parité avec ``LocalSink`` (Go),
    garde-fou anti-évasion d'arborescence inclus.
    """

    root: str = ""

    @classmethod
    def from_env(cls) -> "LocalSink":
        """Construit à partir de DATA_DIR si défini, sinon DEFAULT_DATA_DIR."""
        root = (os.environ.get("DATA_DIR") or "").strip()
        return cls(root=root or DEFAULT_DATA_DIR)

    def write(
        self, key: str, data: bytes, content_type: str, meta: dict[str, str]
    ) -> str:
        """Matérialise l'objet sur disque et renvoie son URI ``file://``.

        Les métadonnées n'ont pas d'équivalent natif sur un FS : elles sont
        ignorées ici (elles restent portées par le manifest). Comportement
        volontaire et documenté, identique à Go.
        """
        del content_type, meta  # non utilisés sur disque ; homogénéité d'interface

        root = (self.root or "").strip() or DEFAULT_DATA_DIR
        rel = key.lstrip("/")  # la clé est une suite de segments séparés par '/'
        abs_root = Path(root).resolve()
        abs_dest = (abs_root / rel).resolve()

        # Garde-fou anti-évasion d'arborescence (la clé ne doit pas sortir de root).
        if abs_dest != abs_root and abs_root not in abs_dest.parents:
            raise ValueError(
                f"storage(local): clé {key!r} sort de la racine {abs_root!r}"
            )

        abs_dest.parent.mkdir(parents=True, exist_ok=True)
        abs_dest.write_bytes(data)
        return abs_dest.as_uri()  # file:///D:/... (gère le préfixe Windows)


@dataclass
class Blob:
    """Artefact prêt à être écrit : nom (dernier segment de clé), contenu, MIME, kind."""

    name: str
    data: bytes
    content_type: str
    kind: ArtifactKind


def blobs_from_fetch(result: FetchResult) -> list[Blob]:
    """Construit la liste standard d'artefacts d'une acquisition HTTP statique.

    Corps brut (RAW_RESPONSE) + échange HTTP sérialisé en JSON (HTTP_EXCHANGE).
    Parité avec ``BlobsFromFetch`` (Go) : le JSON de l'échange est indenté 2 espaces.
    """
    if result is None:
        raise ValueError("storage: FetchResult nil")

    content_type = result.content_type or "application/octet-stream"
    blobs: list[Blob] = [
        Blob(
            name=NAME_RESPONSE,
            data=result.body,
            content_type=content_type,
            kind=ArtifactKind.RAW_RESPONSE,
        )
    ]

    if result.exchange is not None:
        exchange_json = _dump_json(result.exchange)
        blobs.append(
            Blob(
                name=NAME_HTTP_EXCHANGE,
                data=exchange_json,
                content_type="application/json",
                kind=ArtifactKind.HTTP_EXCHANGE,
            )
        )
    return blobs


def store_result(
    sink: Sink,
    command: AcquisitionCommand,
    result: FetchResult,
    blobs: list[Blob],
    final_state: FinalState,
    reasons: list[str],
) -> AcquisitionResult:
    """Écrit le brut + le manifest, puis renvoie le ``AcquisitionResult`` complet.

    Déroulé (parité ``StoreResult`` Go) :
      1. chaque Blob est écrit via le Sink sous sa clé objet (object_key) ;
      2. les métadonnées d'Artifact sont calculées (sha256, taille, clé, URI) ;
      3. le AcquisitionResult est assemblé (état final, mode, échange, observed_at UTC) ;
      4. le manifest (ce même résultat, en JSON) est écrit comme dernier objet.
    """
    if sink is None:
        raise ValueError("storage: sink nil")
    if command is None:
        raise ValueError("storage: commande nil")
    if result is None:
        raise ValueError("storage: FetchResult nil")

    observed_at = datetime.now(timezone.utc)
    meta = _manifest_meta(command, final_state)

    artifacts: list[Artifact] = []
    for blob in blobs:
        key = object_key(command, blob.name)
        uri = sink.write(key, blob.data, blob.content_type, meta)
        artifacts.append(
            Artifact(
                kind=blob.kind,
                content_type=blob.content_type,
                size=len(blob.data),
                sha256=sha256_hex(blob.data),
                key=key,
                uri=uri,
            )
        )

    acquisition_result = AcquisitionResult(
        acquisition_id=command.acquisition_id(),
        final_state=final_state,
        mode=result.mode,
        artifacts=artifacts,
        http_exchange=result.exchange,
        observed_at=observed_at,
        error=_join_reasons(final_state, reasons),
    )

    # Le manifest décrit l'acquisition complète : écrit comme dernier objet, sous la
    # même arborescence (raw/.../<acquisition_id>/manifest.json).
    manifest_key = object_key(command, NAME_MANIFEST)
    manifest_json = _dump_json(acquisition_result)
    sink.write(manifest_key, manifest_json, "application/json", meta)

    return acquisition_result


def _manifest_meta(
    command: AcquisitionCommand, state: FinalState
) -> dict[str, str]:
    """Métadonnées objet attachées à chaque écriture (utiles côté S3). Non-PII (POC)."""
    return {
        "acquisition-id": command.acquisition_id(),
        "final-state": str(state),
    }


def _join_reasons(state: FinalState, reasons: list[str]) -> str:
    """Ne remonte les raisons dans ``error`` que pour les états non-succès (parité Go).

    Ainsi ``error`` reste vide quand tout va bien (et sera omis du JSON).
    """
    if state in (FinalState.SUCCESS, FinalState.UNCHANGED):
        return ""
    if not reasons:
        return ""
    return "; ".join(reasons)


def _dump_json(model: object) -> bytes:
    """Sérialise un modèle pydantic en JSON indenté 2 espaces, avec parité ``omitempty``.

    On exclut les valeurs par défaut/None (champs ``omitempty`` côté Go : chaînes
    vides, dicts vides, ``error`` vide, ``http_exchange`` absent…). Les champs requis
    sans défaut (``acquisition_id``, ``final_state``, ``observed_at``) restent
    toujours présents. ``ensure_ascii=False`` pour garder les accents (comme Go).
    """
    # model_dump(mode="json") applique les field_serializer (ex. observed_at -> "…Z")
    # et rend les enums sous leur valeur nominale ("STATIC", "SUCCESS"…).
    payload = model.model_dump(mode="json", exclude_defaults=True)  # type: ignore[attr-defined]
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    return text.encode("utf-8")


__all__ = [
    "Sink",
    "LocalSink",
    "Blob",
    "blobs_from_fetch",
    "store_result",
    "NAME_RESPONSE",
    "NAME_HTTP_EXCHANGE",
    "NAME_MANIFEST",
    "DEFAULT_DATA_DIR",
]
