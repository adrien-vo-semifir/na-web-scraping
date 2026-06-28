"""Runner MAISON standalone, totalement indépendant de Temporal — miroir de cmd/acquire.

Exécute la tranche d'acquisition (fetch -> validation -> écriture du brut + manifest)
directement, sans démarrer la plateforme ni l'orchestrateur. Preuve concrète de la
RÉVERSIBILITÉ (docs/structure-projet.md §1 & §3.1) : le cœur (core/) est appelable
sans Temporal. AUCUN import du SDK Temporal.

Usage :

    uv run python -m http_fetcher_py.acquire --url https://example.com [--furtif]
                  [--source web] [--dataset pages] [--config-version v1]
                  [--data-dir <chemin>]

Sortie : le AcquisitionResult en JSON sur stdout. Code de sortie : 0 si l'état final
est SUCCESS/UNCHANGED, 1 sinon (BLOCKED / RETRYABLE / PERMANENT), 2 en cas d'erreur
technique (paramètre invalide, échec réseau, échec d'écriture).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from acquisitionv1 import AcquisitionCommand, AcquisitionMode, FinalState

from . import storage
from .fetcher import fetch
from .shared import validate
from .storage import LocalSink, blobs_from_fetch, store_result


def _module_root() -> Path:
    """Racine du module web-scraping (au-dessus de core/http-fetcher-py).

    src/http_fetcher_py/acquire.py -> http_fetcher_py -> src -> http-fetcher-py ->
    core -> <racine module>. Le brut est écrit relativement à cette racine
    (``./data/raw/<clé>``), quel que soit le répertoire courant — conforme à la
    consigne du runner.
    """
    return Path(__file__).resolve().parents[4]


def _build_runner(argv: list[str] | None = None) -> tuple[AcquisitionCommand, LocalSink, bool]:
    """Analyse les arguments et construit la commande + le sink local."""
    parser = argparse.ArgumentParser(
        prog="http_fetcher_py.acquire",
        description="Runner d'acquisition HTTP statique (httpx / curl_cffi furtif), Temporal-free.",
    )
    parser.add_argument("--url", required=True, help="URL à acquérir (obligatoire)")
    parser.add_argument(
        "--furtif",
        action="store_true",
        help="mode furtif : curl_cffi impersonate Chrome (TLS/JA3 + HTTP/2)",
    )
    parser.add_argument("--source", default="web", help="identifiant logique de la source")
    parser.add_argument("--dataset", default="pages", help="jeu de données cible")
    parser.add_argument(
        "--config-version",
        dest="config_version",
        default="v1",
        help="version de configuration (idempotence)",
    )
    parser.add_argument(
        "--data-dir",
        dest="data_dir",
        default=None,
        help="racine d'écriture du brut (défaut : <racine module>/data)",
    )
    args = parser.parse_args(argv)

    command = AcquisitionCommand(
        url=args.url,
        source=args.source,
        dataset=args.dataset,
        mode=AcquisitionMode.STATIC,
        configuration_version=args.config_version,
    )

    data_root = args.data_dir or str(_module_root() / "data")
    sink = LocalSink(root=data_root)
    return command, sink, args.furtif


def run(argv: list[str] | None = None) -> int:
    """Exécute une acquisition complète (fetch -> validate -> store) et imprime le JSON.

    Composition métier identique à platform/acquire.Run (Go) : fetch (core) ->
    validation technique (core) -> écriture du brut + manifest (storage).
    """
    try:
        command, sink, furtif = _build_runner(argv)
    except SystemExit as exc:  # argparse a déjà imprimé l'erreur/usage
        return 2 if exc.code not in (0, None) else int(exc.code or 0)

    try:
        fetched = fetch(command, furtif=furtif)
    except Exception as exc:  # échec réseau / paramètre — erreur technique
        print(f"erreur: acquisition: {exc}", file=sys.stderr)
        return 2

    final_state, reasons = validate(fetched)

    try:
        blobs = blobs_from_fetch(fetched)
        result = store_result(sink, command, fetched, blobs, final_state, reasons)
    except Exception as exc:  # échec d'écriture du brut
        print(f"erreur: écriture du brut: {exc}", file=sys.stderr)
        return 2

    # Imprime le AcquisitionResult JSON (mêmes règles omitempty que le manifest).
    payload = result.model_dump(mode="json", exclude_defaults=True)
    print(json.dumps(payload, indent=2, ensure_ascii=False))

    if result.final_state in (FinalState.SUCCESS, FinalState.UNCHANGED):
        return 0
    print(f"état final non-succès: {result.final_state}", file=sys.stderr)
    return 1


def main() -> None:
    """Point d'entrée console (project.scripts ``acquire`` + ``python -m``)."""
    sys.exit(run())


if __name__ == "__main__":
    main()
