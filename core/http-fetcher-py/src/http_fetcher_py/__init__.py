"""http_fetcher_py — moteur d'acquisition HTTP statique (Python).

Expose une fonction simple « commande -> résultat » : :func:`fetch` effectue une
requête GET réelle (httpx par défaut, curl_cffi en mode furtif), suit les
redirections, et capture l'échange HTTP brut (``HttpExchange``) avec ses timings.

Cœur métier — N'IMPORTE JAMAIS le SDK Temporal (cf. docs/structure-projet.md §1).
Appelable directement (runner ``http_fetcher_py.acquire``) ET, à terme, via une
Activity Temporal — c'est ce qui rend la réversibilité possible.
"""

from .fetcher import (
    DEFAULT_TIMEOUT,
    DEFAULT_USER_AGENT,
    FetchResult,
    fetch,
)

__all__ = [
    "fetch",
    "FetchResult",
    "DEFAULT_TIMEOUT",
    "DEFAULT_USER_AGENT",
]
