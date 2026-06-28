"""Moteur d'acquisition HTTP statique (transport) — équivalent Python de fetcher.go.

Expose ``fetch(command) -> FetchResult`` : requête GET réelle, redirections suivies,
capture de l'échange HTTP brut (``HttpExchange``) avec timings (dns / tls / ttfb /
connect / total, en ms) et protocole négocié.

Deux transports, même forme de sortie :
  - **httpx** (défaut, N1) : HTTP/1.1 + HTTP/2 ;
  - **curl_cffi** (mode *furtif*) : ``impersonate="chrome"`` — empreinte TLS/JA3 et
    HTTP/2 cohérentes d'un vrai Chrome, pour les cibles protégées.

Aucune I/O disque ici : ce moteur est pur transport (parité avec le cœur Go). Le
vocabulaire (``AcquisitionCommand``, ``HttpExchange``, ``AcquisitionMode``) provient
du contrat partagé ``acquisitionv1``. N'IMPORTE JAMAIS Temporal.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import httpx

from acquisitionv1 import AcquisitionCommand, AcquisitionMode, HttpExchange

# Délai maximal d'une acquisition (connexion + lecture du corps), en secondes.
DEFAULT_TIMEOUT: float = 30.0

# Agent par défaut si la commande n'en fournit pas (parité avec le cœur Go).
DEFAULT_USER_AGENT: str = "na-web-scraping/0.1 (+acquisition; POC)"

# Nombre maximal de redirections suivies (parité avec le défaut net/http).
_MAX_REDIRECTS: int = 10


@dataclass
class FetchResult:
    """Sortie du moteur HTTP, agnostique de l'orchestrateur et du stockage.

    ``body`` porte le corps brut de la réponse (l'artefact RAW_RESPONSE) ;
    ``exchange`` porte l'échange HTTP capturé. ``status`` / ``content_type`` /
    ``final_url`` sont des raccourcis pratiques. ``mode`` indique le mode
    d'acquisition (STATIC ici). Miroir du ``FetchResult`` Go.
    """

    body: bytes
    exchange: HttpExchange
    status: int
    content_type: str
    final_url: str
    mode: AcquisitionMode = AcquisitionMode.STATIC
    # Transport effectivement utilisé ("httpx" | "curl_cffi") — diagnostic.
    transport: str = "httpx"


def _merge_headers(headers: dict[str, str] | None) -> dict[str, str]:
    """Applique les en-têtes de la commande puis garantit un User-Agent (parité Go)."""
    merged: dict[str, str] = dict(headers or {})
    has_ua = any(k.lower() == "user-agent" for k in merged)
    if not has_ua:
        merged["User-Agent"] = DEFAULT_USER_AGENT
    return merged


def _ms(seconds: float) -> float:
    """Secondes -> millisecondes (float), conformément au champ ``timings``."""
    return seconds * 1000.0


def fetch(command: AcquisitionCommand, *, furtif: bool = False) -> FetchResult:
    """Acquiert la ressource ``command.url`` en HTTP statique.

    Comportement (parité avec le cœur Go) :
      - méthode GET, redirections suivies (jusqu'à 10) ;
      - en-têtes additionnels de la commande appliqués, User-Agent par défaut sinon ;
      - timeout via :data:`DEFAULT_TIMEOUT` ;
      - capture de l'``HttpExchange`` : méthode, URL initiale/finale, statut,
        en-têtes req/resp, protocole, timings (ms).

    ``furtif=True`` bascule sur curl_cffi (``impersonate="chrome"``) pour présenter
    une empreinte TLS/JA3 + HTTP/2 cohérente d'un vrai navigateur.
    """
    if command is None:  # garde-fou (parité Go : "commande nil")
        raise ValueError("httpfetcher: commande nil")
    if not command.url or not command.url.strip():
        raise ValueError("httpfetcher: url vide")

    if furtif:
        return _fetch_curl_cffi(command)
    return _fetch_httpx(command)


# --------------------------------------------------------------------------- #
# Transport par défaut (N1) : httpx
# --------------------------------------------------------------------------- #
def _fetch_httpx(command: AcquisitionCommand) -> FetchResult:
    """Chemin par défaut : httpx, HTTP/1.1 + HTTP/2, redirections suivies.

    httpx n'expose pas de timings DNS/TLS granulaires de façon portable ; on mesure
    de façon fiable le TTFB (premier octet d'en-tête) et le total (corps lu),
    homogènes avec la référence ``start`` — comme le cœur Go pour ``ttfb`` / ``total``.
    """
    request_headers = _merge_headers(command.headers)

    timeout = httpx.Timeout(DEFAULT_TIMEOUT, connect=10.0)
    start = time.perf_counter()
    ttfb_seconds: float | None = None

    def _record_ttfb(response: httpx.Response) -> None:
        nonlocal ttfb_seconds
        if ttfb_seconds is None:
            ttfb_seconds = time.perf_counter() - start

    with httpx.Client(
        http2=True,
        follow_redirects=True,
        max_redirects=_MAX_REDIRECTS,
        timeout=timeout,
        event_hooks={"response": [_record_ttfb]},
    ) as client:
        response = client.get(command.url, headers=request_headers)
        body = response.content  # force la lecture complète du corps
    total_seconds = time.perf_counter() - start

    final_url = str(response.url)
    content_type = response.headers.get("Content-Type", "")

    timings: dict[str, float] = {}
    if ttfb_seconds is not None:
        timings["ttfb"] = _ms(ttfb_seconds)
    timings["total"] = _ms(total_seconds)

    # httpx normalise la version en "HTTP/1.1" / "HTTP/2" : on garde tel quel.
    protocol = response.http_version or ""

    exchange = HttpExchange(
        method="GET",
        url=command.url,
        final_url=final_url,
        status=response.status_code,
        request_headers=_snapshot_request_headers(response, request_headers),
        response_headers=_flatten_response_headers(response.headers),
        timings=timings,
        protocol=protocol,
    )

    return FetchResult(
        body=body,
        exchange=exchange,
        status=response.status_code,
        content_type=content_type,
        final_url=final_url,
        mode=AcquisitionMode.STATIC,
        transport="httpx",
    )


def _snapshot_request_headers(
    response: httpx.Response, intended: dict[str, str]
) -> dict[str, str]:
    """En-têtes de requête effectivement émis (après transport), avec repli.

    On privilégie ``response.request.headers`` (ce qui est réellement parti), et on
    complète avec l'intention applicative si besoin — proche du snapshot Go.
    """
    out: dict[str, str] = {}
    req = getattr(response, "request", None)
    if req is not None and req.headers is not None:
        for key, value in req.headers.items():
            # httpx présente déjà les valeurs jointes ; on titre-case léger via .title()
            out[_canonical_header(key)] = value
    for key, value in intended.items():
        out.setdefault(_canonical_header(key), value)
    return out


# --------------------------------------------------------------------------- #
# Transport FURTIF : curl_cffi (impersonate Chrome)
# --------------------------------------------------------------------------- #
def _fetch_curl_cffi(command: AcquisitionCommand) -> FetchResult:
    """Mode furtif : curl_cffi avec ``impersonate="chrome"``.

    Présente une empreinte TLS/JA3 et un profil HTTP/2 cohérents d'un vrai Chrome
    (ClientHello, ordre des extensions, ALPN, pseudo-en-têtes) — ce que ne fait pas
    httpx. curl expose en outre des timings précis (namelookup / connect / appconnect
    [TLS] / starttransfer [TTFB] / total), qu'on mappe sur dns / connect / tls / ttfb
    / total (ms) — alignés sur les clés de timings du cœur Go.
    """
    # Import local : n'est requis que pour le chemin furtif (et garde l'import httpx
    # du module fonctionnel même si curl_cffi venait à manquer).
    from curl_cffi import requests as curl_requests

    request_headers = _merge_headers(command.headers)

    response = curl_requests.get(
        command.url,
        headers=request_headers,
        impersonate="chrome",  # TLS/JA3 + HTTP/2 d'un Chrome récent (alias = dernier)
        allow_redirects=True,
        max_redirects=_MAX_REDIRECTS,
        timeout=DEFAULT_TIMEOUT,
    )

    body = response.content
    final_url = str(response.url)
    content_type = response.headers.get("Content-Type", "")
    protocol = _curl_http_version(response)
    timings = _curl_timings(response)

    exchange = HttpExchange(
        method="GET",
        url=command.url,
        final_url=final_url,
        status=response.status_code,
        request_headers={_canonical_header(k): v for k, v in request_headers.items()},
        response_headers=_flatten_curl_headers(response.headers),
        timings=timings,
        protocol=protocol,
    )

    return FetchResult(
        body=body,
        exchange=exchange,
        status=response.status_code,
        content_type=content_type,
        final_url=final_url,
        mode=AcquisitionMode.STATIC,
        transport="curl_cffi",
    )


def _curl_timings(response: object) -> dict[str, float]:
    """Extrait les timings curl et les convertit en ms (clés style Go).

    Deux sources, par ordre de richesse :
      1. ``response.infos`` (dict CURLINFO en secondes) si la version de curl_cffi
         le peuple — on en tire dns / connect / tls / ttfb / total ;
      2. à défaut, ``response.elapsed`` (timedelta) donne au moins ``total``.

    Toute phase non observée est simplement omise (parité avec le cœur Go, où une
    phase non mesurée n'apparaît pas dans la map de timings).
    """
    timings: dict[str, float] = {}

    infos = getattr(response, "infos", None)
    if isinstance(infos, dict) and infos:

        def _put(key_out: str, *candidates: str) -> None:
            for c in candidates:
                val = infos.get(c)
                if isinstance(val, (int, float)) and val > 0:
                    timings[key_out] = _ms(float(val))
                    return

        # CURLINFO_* en secondes (clés telles qu'exposées par curl_cffi).
        _put("dns", "NAMELOOKUP_TIME", "NameLookup")
        _put("connect", "CONNECT_TIME", "Connect")
        _put("tls", "APPCONNECT_TIME", "AppConnect")  # handshake TLS terminé
        _put("ttfb", "STARTTRANSFER_TIME", "StartTransfer")
        _put("total", "TOTAL_TIME", "Total")

    if "total" not in timings:
        elapsed = getattr(response, "elapsed", None)
        total_seconds = getattr(elapsed, "total_seconds", None)
        if callable(total_seconds):
            value = total_seconds()
            if isinstance(value, (int, float)) and value > 0:
                timings["total"] = _ms(float(value))

    return timings


def _curl_http_version(response: object) -> str:
    """Traduit la version HTTP de curl_cffi en libellé "HTTP/x" (parité Go)."""
    version = getattr(response, "http_version", None)
    # curl_cffi expose un int (CURL_HTTP_VERSION_*) ou un enum selon les versions.
    mapping = {
        10: "HTTP/1.0",
        11: "HTTP/1.1",
        20: "HTTP/2",
        30: "HTTP/3",
        # Variantes possibles selon l'exposition (enum .value) :
        1: "HTTP/1.0",
        2: "HTTP/1.1",
        3: "HTTP/2",
        4: "HTTP/3",
    }
    try:
        as_int = int(version)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return str(version) if version else ""
    return mapping.get(as_int, f"HTTP/{as_int}")


# --------------------------------------------------------------------------- #
# Utilitaires d'en-têtes
# --------------------------------------------------------------------------- #
def _canonical_header(name: str) -> str:
    """Canonicalise un nom d'en-tête (Title-Case par segment) — lisibilité du JSON."""
    return "-".join(part.capitalize() for part in name.split("-"))


def _flatten_response_headers(headers: httpx.Headers) -> dict[str, str]:
    """Aplatit les en-têtes de réponse httpx (multi-valeurs jointes par ", ").

    Sémantique HTTP des en-têtes répétés, identique à ``flattenHeaders`` côté Go.
    """
    out: dict[str, str] = {}
    # httpx.Headers.raw préserve les doublons ; on les regroupe et on joint.
    grouped: dict[str, list[str]] = {}
    for raw_key, raw_value in headers.raw:
        key = _canonical_header(raw_key.decode("latin-1"))
        grouped.setdefault(key, []).append(raw_value.decode("latin-1"))
    for key, values in grouped.items():
        out[key] = ", ".join(values)
    return out


def _flatten_curl_headers(headers: object) -> dict[str, str]:
    """Aplatit les en-têtes de réponse curl_cffi en map[str, str] (jointure ", ")."""
    out: dict[str, str] = {}
    # curl_cffi.Headers se comporte comme un multidict ; .items() peut répéter une clé.
    items_fn = getattr(headers, "items", None)
    if items_fn is None:
        return out
    grouped: dict[str, list[str]] = {}
    for key, value in items_fn():
        canon = _canonical_header(str(key))
        grouped.setdefault(canon, []).append(str(value))
    for key, values in grouped.items():
        out[key] = ", ".join(values)
    return out
