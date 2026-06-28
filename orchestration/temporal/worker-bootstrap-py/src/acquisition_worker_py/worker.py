"""Worker bootstrap Python : démarre le Worker qui poll la Task Queue d'acquisition
FURTIVE et exécute l'Activity HTTP statique furtive (core/http-fetcher-py).

Composition root de la couche d'orchestration côté Python (docs/structure-projet.md
§3.3) : c'est l'un des rares mains autorisés à câbler ensemble Temporal et le code
métier. Un Worker Temporal est mono-langage ; ce bootstrap est celui du langage Python.
Le Worker Go (``worker-bootstrap/main.go``) porte les Workflows et l'Activity Go ; le
Worker TS porte l'Activity navigateur ; CE Worker Python porte l'Activity HTTP statique
furtive et poll SA Task Queue. Le routage inter-langages passe par la Task Queue (le
Workflow Go cible ``acquisition-py`` pour les acquisitions furtives), pas par un appel
direct entre Workers.

CONVENTIONS IMPOSÉES (le Workflow Go s'y conforme, NE PAS les changer) :
  - Nom d'activité enregistré : "AcquireActivity"   (cf. activity.defn name=…)
  - Task Queue                : "acquisition-py"
  - Namespace                 : "default"
  - Data converter            : JSON par défaut (snake_case, enums nominales)

Configuration par environnement :
  TEMPORAL_ADDRESS  adresse du frontend Temporal (défaut 127.0.0.1:7233)
  DATA_DIR          racine d'écriture du brut (défaut : ./data à la racine du module)

Lancement :  uv run python -m acquisition_worker_py
        ou :  uv run acquisition-worker-py
"""

from __future__ import annotations

import asyncio
import os
import signal
from pathlib import Path

from temporalio.client import Client
from temporalio.worker import Worker

from acquire_activity_py import AcquireActivity

# TASK_QUEUE — Task Queue du Worker Python. Valeur IMPOSÉE par la convention de routage :
# le Workflow Go appelle ExecuteActivity("AcquireActivity", command,
# {taskQueue:"acquisition-py"}) pour les acquisitions furtives. Figée (pas via env) pour
# garder le contrat de routage stable, comme l'homologue TS ("acquisition-ts").
TASK_QUEUE = "acquisition-py"

# NAMESPACE — namespace Temporal. "default" est créé d'office par temporalio/auto-setup
# (cf. compose.yaml), comme côté Go et TS.
NAMESPACE = "default"

# DEFAULT_TEMPORAL_ADDRESS — frontend Temporal local du POC (cf. compose.yaml, port 7233).
DEFAULT_TEMPORAL_ADDRESS = "127.0.0.1:7233"


def _module_root() -> Path:
    """Racine du module web-scraping, depuis worker-bootstrap-py/src/acquisition_worker_py/.

    .../worker.py[0] -> acquisition_worker_py[0] -> src[1] -> worker-bootstrap-py[2]
    -> temporal[3] -> orchestration[4] -> <racine module>[5]. Le ``LocalSink`` de
    l'Activity écrit sous ``./data`` RELATIF au cwd du process (même convention que
    ``NewLocalSink`` Go) : on fixe donc le cwd à cette racine pour que le brut atterrisse
    dans ``modules/web-scraping/data``, quel que soit le répertoire de lancement.
    ``DATA_DIR`` (env) reste prioritaire et inchangé.
    """
    return Path(__file__).resolve().parents[5]


async def run() -> None:
    """Connexion au frontend Temporal, démarrage du Worker, poll jusqu'à l'arrêt.

    Data converter JSON par défaut (non surchargé) : le ``command`` reçu est du JSON à
    la forme Go (snake_case, enums nominales) et le ``AcquisitionResult`` ressort à
    l'identique (l'Activity renvoie le dict ``model_dump(mode="json",
    exclude_defaults=True)``, transmis tel quel).
    """
    # Aligne le cwd sur la racine du module : le Sink local de l'Activity dérive ``./data``
    # de ce cwd (sauf si DATA_DIR est défini, auquel cas il prime).
    module_root = _module_root()
    os.chdir(module_root)

    address = os.getenv("TEMPORAL_ADDRESS", DEFAULT_TEMPORAL_ADDRESS).strip() or DEFAULT_TEMPORAL_ADDRESS

    # Client.connect : data converter JSON par défaut (pas de surcharge). namespace="default".
    client = await Client.connect(address, namespace=NAMESPACE)

    data_dir = os.getenv("DATA_DIR", "").strip() or str(module_root / "data")
    print(
        "worker-bootstrap-py: Worker Python démarré "
        f"(temporal={address}, namespace={NAMESPACE}, task_queue={TASK_QUEUE}, "
        f"activity=AcquireActivity, data_dir={data_dir})",
        flush=True,
    )

    # Arrêt propre : un Event déclenché par SIGINT/SIGTERM stoppe le Worker (drain des
    # tâches en cours). Worker.run() prend en charge le shutdown via ce gestionnaire de
    # contexte async. Sous Windows, add_signal_handler n'est pas supporté par la boucle
    # asyncio : on retombe alors sur signal.signal.
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _request_stop() -> None:
        loop.call_soon_threadsafe(stop_event.set)

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            # Windows ProactorEventLoop : pas d'add_signal_handler -> fallback portable.
            signal.signal(sig, lambda *_: _request_stop())

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        # Le nom D'ENREGISTREMENT de l'Activity est fixé par @activity.defn(name=…) à
        # "AcquireActivity", exactement ce qu'attend le Workflow Go.
        activities=[AcquireActivity],
    ):
        # Bloque jusqu'au signal d'arrêt, puis le `async with` draine et ferme le Worker.
        await stop_event.wait()

    print("worker-bootstrap-py: arrêt propre du Worker.", flush=True)


def main() -> None:
    """Point d'entrée console (project.scripts ``acquisition-worker-py`` + ``python -m``)."""
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        # Filet de sécurité : interruption avant l'installation des gestionnaires.
        pass


if __name__ == "__main__":
    main()
