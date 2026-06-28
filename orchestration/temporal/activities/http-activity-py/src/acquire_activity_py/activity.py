"""Enveloppe d'Activity Temporal du moteur HTTP statique FURTIF (core/http-fetcher-py).

Une enveloppe d'Activity est MINCE par conception (docs/structure-projet.md §3.3) :
elle reconstruit la commande, appelle la composition métier de ``core/`` (fetch →
validation → écriture du brut + manifest), et remonte le résultat. Toute la logique
d'acquisition vit dans ``core/`` ; cette couche est, avec le reste
d'``orchestration/temporal/``, le SEUL endroit autorisé à connaître l'orchestrateur —
et encore, ici on n'importe le SDK que pour le log d'Activity.

Pendant Python de l'enveloppe Go ``http-activity-go`` (``AcquireActivity``) et de
l'enveloppe TS ``browser-activity-ts``, pour le moteur HTTP statique en mode FURTIF.
Le routage inter-langages se fait par la Task Queue : le Workflow Go appelle
``ExecuteActivity("AcquireActivity", command, {taskQueue:"acquisition-py"})`` pour les
acquisitions furtives (mode=STATIC + en-tête furtif) ; ce Worker Python poll
``acquisition-py``.

RÉVERSIBILITÉ : l'enveloppe importe le SDK Temporal (toléré sous
``orchestration/temporal/``), mais le moteur (``core/``) n'en sait rien. Si l'on
abandonne Temporal, on jette ce fichier sans toucher à ``core/http-fetcher-py``.

CONTRAT JSON (data converter JSON par défaut, cf. worker-bootstrap-py) :
  - ``command`` arrive du data converter sous la forme EXACTE du Go : un objet JSON à
    champs ``snake_case`` (``url``, ``configuration_version``, …) et enums en forme
    nominale (``"STATIC"``). On le désérialise via le modèle pydantic du contrat
    (``contracts/gen/python``), dont les champs sont déjà en snake_case et dont les
    enums sont des ``str``-enums nominales : la reconstruction est donc directe.
  - Le résultat ressort en JSON de MÊME forme que le Go : ``snake_case``, enums
    nominales, ``observed_at`` RFC3339 « …Z », et surtout MÊMES règles ``omitempty``
    que le manifest. Pour le garantir sans dépendre des détails du convertisseur
    Temporal, l'Activity renvoie explicitement le dict produit par
    ``model_dump(mode="json", exclude_defaults=True)`` — la MÊME sérialisation que
    ``storage._dump_json`` / ``acquire.run`` (donc identique, octet pour octet, au
    ``manifest.json`` déjà écrit sous ``data/raw/``). Le data converter JSON par
    défaut transmet ce dict tel quel.
"""

from __future__ import annotations

from typing import Any

from temporalio import activity

from acquisitionv1 import AcquisitionCommand

# Réutilisation directe du cœur métier (core/http-fetcher-py) : AUCUNE logique ici.
from http_fetcher_py.fetcher import fetch
from http_fetcher_py.shared import validate
from http_fetcher_py.storage import LocalSink, blobs_from_fetch, store_result

# Nom d'enregistrement IMPOSÉ de l'Activity. Le Workflow Go appelle
# ExecuteActivity("AcquireActivity", …) : la chaîne doit correspondre exactement.
ACTIVITY_NAME = "AcquireActivity"

# Ce Worker est le Worker FURTIF : le moteur HTTP statique est invoqué en mode furtif
# (curl_cffi impersonate Chrome — TLS/JA3 + HTTP/2 cohérents). Constante de clarté.
_FURTIF = True


def _to_command(command: Any) -> AcquisitionCommand:
    """Reconstruit une ``AcquisitionCommand`` depuis la charge JSON reçue.

    Le data converter JSON par défaut décode l'objet JSON en ``dict`` (forme Go :
    snake_case, enums nominales). Les champs du modèle pydantic du contrat sont en
    snake_case et ses enums sont des ``str``-enums nominales : ``model_validate``
    accepte donc directement ce dict, sans remapping. Tolère aussi qu'un
    ``AcquisitionCommand`` soit déjà fourni (appel direct / test).
    """
    if command is None:
        raise ValueError("AcquireActivity: commande nil")
    if isinstance(command, AcquisitionCommand):
        return command
    if isinstance(command, dict):
        return AcquisitionCommand.model_validate(command)
    raise TypeError(
        f"AcquireActivity: commande de type inattendu {type(command)!r} "
        "(attendu: objet JSON / dict)"
    )


@activity.defn(name=ACTIVITY_NAME)
async def AcquireActivity(command: Any) -> dict[str, Any]:
    """Enveloppe d'Activity du moteur HTTP statique furtif.

    Déroulé (identique à ``platform/acquire.Run`` + ``StoreResult`` côté Go, et au
    runner ``http_fetcher_py.acquire``) :

      1. ``fetch(command, furtif=True)`` — requête HTTP statique furtive (curl_cffi),
         capture de l'échange (core, sans I/O disque) ;
      2. ``validate`` — état final normalisé (SUCCESS / BLOCKED / RETRYABLE / PERMANENT) ;
      3. ``store_result`` — écriture des artefacts (corps brut + échange) et du manifest
         via le Sink local (MÊME clé objet que le Go : ``object_key`` réutilisé tel quel).

    Le Sink est un ``LocalSink`` construit depuis l'environnement (``DATA_DIR`` si
    défini, sinon ``./data`` relatif au cwd — que le bootstrap fixe à la racine du
    module, comme ``NewLocalSink`` Go / ``LocalSink`` TS).

    Renvoie le ``AcquisitionResult`` en JSON (dict) de MÊME forme que le Go.
    L'erreur éventuelle est une erreur applicative classique ; la politique de reprise
    (retries) est définie côté Workflow, pas ici.
    """
    cmd = _to_command(command)

    # Log d'Activity (no-op hors contexte Temporal, ex. test direct) — seul usage du SDK.
    if activity.in_activity():
        activity.logger.info(
            "acquisition démarrée",
            extra={"url": cmd.url, "acquisition_id": cmd.acquisition_id()},
        )

    # Sink local : DATA_DIR (env) prioritaire, sinon ./data relatif au cwd du worker
    # (le bootstrap fixe ce cwd à la racine du module). Convention de clé identique au Go.
    sink = LocalSink.from_env()

    # core/ : transport FURTIF par défaut sur ce Worker (curl_cffi impersonate Chrome).
    fetched = fetch(cmd, furtif=_FURTIF)
    final_state, reasons = validate(fetched)
    blobs = blobs_from_fetch(fetched)
    result = store_result(sink, cmd, fetched, blobs, final_state, reasons)

    # Sérialisation EXACTE du manifest (omitempty / observed_at "…Z" / enums nominales) :
    # mêmes règles que storage._dump_json — garantit la parité de forme avec le Go,
    # indépendamment du convertisseur Temporal (qui transmet ce dict tel quel).
    return result.model_dump(mode="json", exclude_defaults=True)


__all__ = ["AcquireActivity", "ACTIVITY_NAME"]
