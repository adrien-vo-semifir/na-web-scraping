import hashlib, time, os, json
from urllib.parse import urlparse
import httpx
import brotli            # noqa: F401  (décodeur br pour httpx N1 — sinon corps compressé illisible)
import zstandard         # noqa: F401  (décodeur zstd pour httpx N1)
from curl_cffi import requests as creq
from playwright.sync_api import sync_playwright
import boto3
from botocore.config import Config as _BotoConfig

CHROME_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
N1_HEADERS = {"User-Agent": CHROME_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7", "Accept-Encoding": "gzip, deflate, br, zstd",
    "sec-ch-ua": '"Chromium";v="131", "Google Chrome";v="131", "Not_A Brand";v="24"',
    "sec-ch-ua-mobile": "?0", "sec-ch-ua-platform": '"Windows"',
    "Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1", "Upgrade-Insecure-Requests": "1"}
CHALLENGE = ["cf-challenge", "just a moment...", "checking your browser", "attention required",
             "verifying you are human", "datadome", "_incapsula_resource", "px-captcha"]
MAP_STATE = {"success": "SUCCESS", "incomplete_spa": "BLOCKED", "blocked": "BLOCKED",
             "permanent": "PERMANENT", "retryable": "RETRYABLE"}

def _fetch(url, rank):
    ua = CHROME_UA
    if rank == "http":
        with httpx.Client(follow_redirects=True, timeout=30, headers=N1_HEADERS) as c:
            r = c.get(url)
        return r.status_code, dict(r.headers), (r.text or ""), str(r.http_version)
    if rank == "curl_cffi":
        with creq.Session() as s:
            r = s.get(url, impersonate="chrome", timeout=30)
        return r.status_code, dict(r.headers), (r.text or ""), "curl_cffi(chrome)"
    if rank == "browser":
        cpath = os.environ.get("CHROMIUM_PATH", "/usr/bin/chromium")
        try:
            with sync_playwright() as pw:
                b = pw.chromium.launch(executable_path=cpath, args=["--no-sandbox",
                    "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"])
                ctx = b.new_context(user_agent=CHROME_UA, locale="fr-FR",
                                    timezone_id="Europe/Paris", viewport={"width": 1920, "height": 1080})
                ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
                pg = ctx.new_page()
                resp = pg.goto(url, timeout=30000, wait_until="networkidle")
                html = pg.content(); status = resp.status if resp else 200
                headers = dict(resp.headers) if resp else {"content-type": "text/html"}
                b.close()
            return status, headers, html, "playwright(chromium, stealth)"
        except Exception as e:
            return -1, {}, "", "browser KO: %s" % e
    if rank == "stealth":
        return -1, {}, "", "furtif Camoufox/nodriver : worker dédié requis (N4)"
    return -1, {}, "", "rang inconnu"

def _classify(rank, status, ct, body):
    ct = (ct or "").lower(); low = body.lower()
    if status == -1: return "blocked"
    if "\x00" in body and ("html" in ct or "text" in ct or not ct):  # corps binaire/compressé non décodé
        return "blocked"
    if status in (403, 429) or (("text/html" in ct or not ct) and any(m in low for m in CHALLENGE)):
        return "blocked"
    if status >= 500: return "retryable"
    if status >= 400: return "permanent"
    spa = any(m in low for m in ['id="root"', 'id="__next"', '__next_data__', 'window.__nuxt'])
    if rank in ("http", "curl_cffi") and spa and len(body.strip()) < 2000: return "incomplete_spa"
    return "success"

def _store_s3(source, dataset, day, acq_id, final_state, body_bytes, exchange, manifest):
    if not os.environ.get("S3_ENDPOINT"): return []
    s3 = boto3.client("s3", endpoint_url=os.environ["S3_ENDPOINT"],
        aws_access_key_id=os.environ.get("S3_ACCESS_KEY_ID", "any"),
        aws_secret_access_key=os.environ.get("S3_SECRET_ACCESS_KEY", "any"),
        region_name=os.environ.get("S3_REGION", "us-east-1"),
        config=_BotoConfig(s3={"addressing_style": "path"}))
    bucket = os.environ.get("S3_BUCKET", "lake")
    data_zone = "raw" if final_state in ("SUCCESS", "UNCHANGED") else "rejected"
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

# Une TENTATIVE à un rang. chosen=True si succès/définitif OU dernier rang -> écrit S3 + stoppe la boucle.
def main(rank: str, url: str, is_last: bool = False, source: str = "web",
         dataset: str = "pages", configuration_version: str = "v1"):
    acq_id = hashlib.sha256(("%s|%s" % (url, configuration_version)).encode()).hexdigest()[:16]
    status, headers, body, proto = _fetch(url, rank)
    cls = _classify(rank, status, headers.get("content-type", ""), body)
    escalate = cls in ("blocked", "incomplete_spa")
    chosen = (not escalate) or bool(is_last)
    out = {"chosen": chosen, "rang": rank, "status": status, "protocol": proto, "classification": cls}
    if not chosen:
        return out                                  # bloqué/incomplet -> on escalade (rang suivant)
    observed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    final_state = MAP_STATE.get(cls, "PERMANENT")
    enc = body.encode("utf-8", "ignore"); ct = headers.get("content-type", "")
    exchange = {"method": "GET", "url": url, "status": status, "content_type": ct,
                "protocol": proto, "observed_at": observed_at}
    manifest = {"acquisition_id": acq_id, "url": url, "source": source, "dataset": dataset,
                "configuration_version": configuration_version, "observed_at": observed_at,
                "final_state": final_state, "rang_used": rank, "content_type": ct,
                "http": {"status": status, "protocol": proto, "content_type": ct,
                         "body_len": len(enc), "body_sha256": hashlib.sha256(enc).hexdigest()}}
    s3_uris = _store_s3(source, dataset, observed_at[:10], acq_id, final_state, enc, exchange, manifest)
    out.update({"acquisition_id": acq_id, "url": url, "final_state": final_state, "rang_used": rank,
                "observed_at": observed_at, "http": manifest["http"], "s3_uris": s3_uris})
    return out