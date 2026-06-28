"""Utilitaires techniques communs — équivalent Python de core/shared/shared.go.

Validation technique du résultat, empreinte de contenu, dérivation de la clé objet.
Cœur métier — N'IMPORTE JAMAIS le SDK Temporal.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from acquisitionv1 import AcquisitionCommand, FinalState

from .fetcher import FetchResult


def sha256_hex(data: bytes) -> str:
    """Empreinte SHA-256 du contenu, en hexadécimal minuscule (dédup / intégrité)."""
    return hashlib.sha256(data).hexdigest()


def _segment(value: str) -> str:
    """Normalise un fragment de clé : vide -> "_", séparateurs de chemin neutralisés.

    Évite toute injection de niveau d'arborescence (parité avec ``segment`` Go).
    """
    value = (value or "").strip()
    if value == "":
        return "_"
    return value.replace("/", "_").replace("\\", "_")


def object_key(command: AcquisitionCommand, name: str) -> str:
    """Construit la clé objet d'un artefact selon la convention du lac :

        raw/<source>/<dataset>/<YYYY-MM-DD>/<acquisition_id>/<name>

    La date (UTC) est celle du jour d'acquisition. ``source`` / ``dataset`` absents
    sont remplacés par "_" (arborescence stable et non vide). Strictement identique
    à ``ObjectKey`` (Go) : même ordre, même format de date, même ``acquisition_id``.
    """
    source = _segment(command.source)
    dataset = _segment(command.dataset)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return "/".join(
        ["raw", source, dataset, day, command.acquisition_id(), name]
    )


# Signatures textuelles fréquentes de pages de protection (parité 1:1 avec Go).
# Liste indicative (POC) ; l'inventaire CAPTCHA complet vit dans docs/audit-captcha/.
_CHALLENGE_MARKERS: tuple[str, ...] = (
    "cf-challenge",  # Cloudflare
    "cf_chl_opt",  # Cloudflare challenge
    "just a moment...",  # Cloudflare interstitiel
    "checking your browser",  # anti-bot générique
    "attention required",  # Cloudflare 1020 / WAF
    "verifying you are human",  # challenge générique
    "enable javascript and cookies",
    "_incapsula_resource",  # Imperva / Incapsula
    "distil_r_captcha",  # Distil Networks
    "px-captcha",  # PerimeterX
    "g-recaptcha",  # Google reCAPTCHA
    "h-captcha",  # hCaptcha
    "datadome",  # DataDome
)

# Au-delà de 256 Kio, un corps HTML est considéré comme du contenu réel (pas un
# challenge). Parité avec ``maxChallengeBytes`` côté Go.
_MAX_CHALLENGE_BYTES: int = 256 * 1024


def _is_challenge(result: FetchResult) -> bool:
    """Heuristique conservatrice : petit corps HTML contenant un marqueur connu.

    Ne déclenche que sur des corps HTML de taille modérée pour éviter les faux
    positifs sur de gros documents légitimes (parité ``isChallenge`` Go).
    """
    content_type = (result.content_type or "").lower()
    is_html = "text/html" in content_type or content_type == ""
    if not is_html:
        return False
    if len(result.body) == 0 or len(result.body) > _MAX_CHALLENGE_BYTES:
        return False
    lowered = result.body.decode("utf-8", errors="ignore").lower()
    return any(marker in lowered for marker in _CHALLENGE_MARKERS)


def validate(result: FetchResult | None) -> tuple[FinalState, list[str]]:
    """Validation TECHNIQUE d'un résultat d'acquisition (parité ``Validate`` Go).

    Règles (POC, transport HTTP) :
      - 403 ou 429                          -> BLOCKED (protection / WAF / rate-limit)
      - corps ressemblant à un challenge    -> BLOCKED (CAPTCHA / JS challenge)
      - 5xx                                 -> RETRYABLE (échec transitoire serveur)
      - autres 4xx                          -> PERMANENT (échec définitif requête)
      - 2xx / 3xx sans challenge            -> SUCCESS

    ``reasons`` est toujours renseigné (au moins un message décrivant la décision).
    """
    if result is None:
        return FinalState.PERMANENT, ["résultat nil"]

    status = result.status
    reasons: list[str] = []

    if status in (403, 429):
        reasons.append(f"statut {status} (protection / limitation)")
        return FinalState.BLOCKED, reasons

    if _is_challenge(result):
        reasons.append(
            "corps de réponse détecté comme page de challenge (CAPTCHA / JS challenge)"
        )
        return FinalState.BLOCKED, reasons

    if status >= 500:
        reasons.append(f"statut {status} (erreur serveur, transitoire)")
        return FinalState.RETRYABLE, reasons

    if status >= 400:
        reasons.append(f"statut {status} (erreur de requête, définitive)")
        return FinalState.PERMANENT, reasons

    reasons.append(f"statut {status}, contenu accepté")
    return FinalState.SUCCESS, reasons


__all__ = ["sha256_hex", "object_key", "validate"]
