import hashlib, time, os
from urllib.parse import urlparse
import httpx
from curl_cffi import requests as creq
from playwright.sync_api import sync_playwright
import json
try:
    import playwright_stealth  # auto-installé par Windmill ; patches stealth (best effort)
except Exception:
    playwright_stealth = None
import boto3                                  # top-level -> Windmill installe le paquet (+ botocore)
from botocore.config import Config as _BotoConfig

# Étape 1 — CASCADE D'ESCALADE (équivalent du corps de workflow d'acquisition).
# Rangs N1->N4 (managé N5 = SaaS, hors socle). N1/N2 = fetch réel ; N3/N4 = worker dédié (marqueur).
LADDER = ["http", "curl_cffi", "browser", "stealth"]
KNOWN_PROTECTED = {"datadome.co", "nike.com", "g2.com"}  # policy par domaine (mémoire) : entrée directe furtif
CHALLENGE = ["cf-challenge", "just a moment...", "checking your browser", "attention required",
             "verifying you are human", "datadome", "_incapsula_resource", "px-captcha"]

# --- Config « règles de l'art » ---
CHROME_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
# N1 : en-têtes COMPLETS et réalistes (pas juste l'UA) — content negotiation + bat les heuristiques « header manquant ».
N1_HEADERS = {
    "User-Agent": CHROME_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "sec-ch-ua": '"Chromium";v="131", "Google Chrome";v="131", "Not_A Brand";v="24"',
    "sec-ch-ua-mobile": "?0", "sec-ch-ua-platform": '"Windows"',
    "Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none", "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

def _apply_stealth(page):
    # API de playwright-stealth variable selon la version -> robuste, et no-op si absente.
    if playwright_stealth is None:
        return
    if hasattr(playwright_stealth, "stealth_sync"):
        playwright_stealth.stealth_sync(page)
    elif hasattr(playwright_stealth, "Stealth"):
        playwright_stealth.Stealth().apply_stealth_sync(page)


# Sink S3 (SeaweedFS au POC / Ceph RGW en prod) — écrit le triplet response/http_exchange/manifest.
MAP_STATE = {"success": "SUCCESS", "incomplete_spa": "BLOCKED", "blocked": "BLOCKED",
             "permanent": "PERMANENT", "retryable": "RETRYABLE"}

def _store_s3(source, dataset, day, acq_id, body_bytes, exchange, manifest):
    if boto3 is None or not os.environ.get("S3_ENDPOINT"):
        return []                                  # pas de S3 configuré -> on n'écrit pas
    s3 = boto3.client("s3", endpoint_url=os.environ["S3_ENDPOINT"],
                      aws_access_key_id=os.environ.get("S3_ACCESS_KEY_ID", "any"),
                      aws_secret_access_key=os.environ.get("S3_SECRET_ACCESS_KEY", "any"),
                      region_name=os.environ.get("S3_REGION", "us-east-1"),
                      config=_BotoConfig(s3={"addressing_style": "path"}))
    bucket = os.environ.get("S3_BUCKET", "lake")
    # Données -> raw (succès) | rejected (échec) ; manifest -> metadata (index + lignage).
    data_zone = "raw" if manifest.get("final_state") in ("SUCCESS", "UNCHANGED") else "rejected"
    acq = "%s/%s/%s/%s" % (source, dataset, day, acq_id)
    uris = []
    for name, data, ct, zone in [
        ("response.bin", body_bytes, manifest.get("content_type") or "application/octet-stream", data_zone),
        ("http_exchange.json", json.dumps(exchange, ensure_ascii=False).encode("utf-8"), "application/json", data_zone),
        ("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"), "application/json", "metadata"),
    ]:
        key = "%s/%s/%s" % (zone, acq, name)
        s3.put_object(Bucket=bucket, Key=key, Body=data, ContentType=ct)
        uris.append("s3://%s/%s" % (bucket, key))
    return uris

def _fetch(url, rank):
    if rank == "http":
        with httpx.Client(follow_redirects=True, timeout=30, headers=N1_HEADERS) as c:
            r = c.get(url)
        return r.status_code, dict(r.headers), (r.text or ""), str(r.http_version)
    if rank == "curl_cffi":
        # Session (réutilisation cookie/connexion) + impersonate ; on NE force PAS l'UA
        # (curl_cffi pose UA + en-têtes + ordre cohérents). Réutilisation cross-pages = cache Valkey (à venir).
        with creq.Session() as s:
            r = s.get(url, impersonate="chrome", timeout=30)
        return r.status_code, dict(r.headers), (r.text or ""), "curl_cffi(chrome)"
    if rank == "browser":
        cpath = os.environ.get("CHROMIUM_PATH", "/usr/bin/chromium")
        try:
            with sync_playwright() as pw:
                # Flags PROPRES : on retire --single-process/--disable-gpu (non-navigateur, détectables)
                # et on désactive AutomationControlled (supprime navigator.webdriver).
                b = pw.chromium.launch(executable_path=cpath, args=[
                    "--no-sandbox", "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled"])
                # Contexte COHÉRENT : UA Chrome réel (plus la string bot), locale/timezone/viewport.
                ctx = b.new_context(user_agent=CHROME_UA, locale="fr-FR",
                                    timezone_id="Europe/Paris", viewport={"width": 1920, "height": 1080})
                ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
                                    "window.chrome=window.chrome||{runtime:{}};")
                pg = ctx.new_page()
                try:
                    _apply_stealth(pg)          # patches complets si la lib est dispo
                except Exception:
                    pass                        # sinon on garde les patches manuels ci-dessus
                resp = pg.goto(url, timeout=30000, wait_until="networkidle")
                html = pg.content()
                status = resp.status if resp else 200
                headers = dict(resp.headers) if resp else {"content-type": "text/html"}
                b.close()
            return status, headers, html, "playwright(chromium, stealth)"
        except Exception as e:
            return -1, {}, "", f"browser KO: {e}"
    if rank == "stealth":
        return -1, {}, "", "furtif Camoufox/nodriver : worker dédié requis (N4)"
    return -1, {}, "", "rang inconnu"

def _classify(rank, status, ct, body):
    ct = (ct or "").lower(); low = body.lower()
    if status == -1:
        return "blocked"                       # moteur indisponible -> escalade
    if status in (403, 429) or (("text/html" in ct or not ct) and any(m in low for m in CHALLENGE)):
        return "blocked"                       # protection / challenge -> escalade
    if status >= 500:
        return "retryable"
    if status >= 400:
        return "permanent"
    spa = any(m in low for m in ['id="root"', 'id="__next"', '__next_data__', 'window.__nuxt'])
    if rank in ("http", "curl_cffi") and spa and len(body.strip()) < 2000:
        return "incomplete_spa"                # SPA non rendu -> escalade vers navigateur
    return "success"

def main(url: str, source: str = "web", dataset: str = "pages",
         configuration_version: str = "v1", entry_rank: str = "auto", max_rank: str = "stealth"):
    acquisition_id = hashlib.sha256(f"{url}|{configuration_version}".encode()).hexdigest()[:16]
    host = (urlparse(url).hostname or "").lower()
    if entry_rank == "auto":
        start = "curl_cffi" if any(host == d or host.endswith("." + d) for d in KNOWN_PROTECTED) else "http"
    else:
        start = entry_rank
    ladder = LADDER[LADDER.index(start): LADDER.index(max_rank) + 1]
    attempts, chosen, chosen_enc = [], None, b""
    for rank in ladder:
        status, headers, body, proto = _fetch(url, rank)
        cls = _classify(rank, status, headers.get("content-type", ""), body)
        enc = body.encode("utf-8", "ignore")
        chosen_enc = enc                       # corps complet du rang retenu (pour S3)
        chosen = {"rang": rank, "status": status, "protocol": proto, "classification": cls,
                  "content_type": headers.get("content-type", ""), "body_len": len(enc),
                  "body_sha256": hashlib.sha256(enc).hexdigest(), "body_preview": body[:500]}
        attempts.append({k: chosen[k] for k in ("rang", "status", "classification", "protocol")})
        if cls in ("success", "permanent", "retryable"):
            break                              # on n'escalade que si bloqué / incomplet

    observed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    day = observed_at[:10]
    final_state = MAP_STATE.get(chosen["classification"], "PERMANENT")
    exchange = {"method": "GET", "url": url, "status": chosen["status"],
                "content_type": chosen["content_type"], "protocol": chosen["protocol"],
                "observed_at": observed_at}
    manifest = {"acquisition_id": acquisition_id, "url": url, "source": source, "dataset": dataset,
                "configuration_version": configuration_version, "observed_at": observed_at,
                "final_classification": chosen["classification"], "final_state": final_state,
                "rang_used": chosen["rang"], "content_type": chosen["content_type"],
                "http": {"status": chosen["status"], "protocol": chosen["protocol"],
                         "content_type": chosen["content_type"], "body_len": chosen["body_len"],
                         "body_sha256": chosen["body_sha256"]}}
    s3_uris = _store_s3(source, dataset, day, acquisition_id, chosen_enc, exchange, manifest)
    return {"acquisition_id": acquisition_id, "url": url, "source": source, "dataset": dataset,
            "configuration_version": configuration_version, "observed_at": observed_at,
            "entry": start, "ladder": ladder, "attempts": attempts, "rang_used": chosen["rang"],
            "final_classification": chosen["classification"],
            "status": chosen["status"], "protocol": chosen["protocol"],
            "content_type": chosen["content_type"], "body_len": chosen["body_len"],
            "body_sha256": chosen["body_sha256"], "body_preview": chosen["body_preview"],
            "s3_uris": s3_uris}