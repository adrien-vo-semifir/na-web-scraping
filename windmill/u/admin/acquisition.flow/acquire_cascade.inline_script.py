import hashlib, time, os
from urllib.parse import urlparse
import httpx
from curl_cffi import requests as creq
from playwright.sync_api import sync_playwright

# Étape 1 — CASCADE D'ESCALADE (équivalent du corps de workflow d'acquisition).
# Rangs N1->N4 (managé N5 = SaaS, hors socle). N1/N2 = fetch réel ; N3/N4 = worker dédié (marqueur).
LADDER = ["http", "curl_cffi", "browser", "stealth"]
KNOWN_PROTECTED = {"datadome.co", "nike.com", "g2.com"}  # policy par domaine (mémoire) : entrée directe furtif
CHALLENGE = ["cf-challenge", "just a moment...", "checking your browser", "attention required",
             "verifying you are human", "datadome", "_incapsula_resource", "px-captcha"]

def _fetch(url, rank):
    ua = "na-web-scraping/0.1 (+acquisition; POC)"
    if rank == "http":
        with httpx.Client(follow_redirects=True, timeout=30, headers={"User-Agent": ua}) as c:
            r = c.get(url)
        return r.status_code, dict(r.headers), (r.text or ""), str(r.http_version)
    if rank == "curl_cffi":
        r = creq.get(url, impersonate="chrome", timeout=30)
        return r.status_code, dict(r.headers), (r.text or ""), "curl_cffi(chrome)"
    if rank == "browser":
        cpath = os.environ.get("CHROMIUM_PATH", "/usr/bin/chromium")
        try:
            with sync_playwright() as pw:
                b = pw.chromium.launch(executable_path=cpath, args=["--no-sandbox",
                    "--disable-dev-shm-usage", "--disable-gpu", "--single-process", "--no-zygote"])
                pg = b.new_page(user_agent=ua)
                resp = pg.goto(url, timeout=30000, wait_until="networkidle")
                html = pg.content()
                status = resp.status if resp else 200
                headers = dict(resp.headers) if resp else {"content-type": "text/html"}
                b.close()
            return status, headers, html, "playwright(chromium)"
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
    attempts, chosen = [], None
    for rank in ladder:
        status, headers, body, proto = _fetch(url, rank)
        cls = _classify(rank, status, headers.get("content-type", ""), body)
        enc = body.encode("utf-8", "ignore")
        chosen = {"rang": rank, "status": status, "protocol": proto, "classification": cls,
                  "content_type": headers.get("content-type", ""), "body_len": len(enc),
                  "body_sha256": hashlib.sha256(enc).hexdigest(), "body_preview": body[:500]}
        attempts.append({k: chosen[k] for k in ("rang", "status", "classification", "protocol")})
        if cls in ("success", "permanent", "retryable"):
            break                              # on n'escalade que si bloqué / incomplet
    return {"acquisition_id": acquisition_id, "url": url, "source": source, "dataset": dataset,
            "configuration_version": configuration_version,
            "observed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "entry": start, "ladder": ladder, "attempts": attempts, "rang_used": chosen["rang"],
            "final_classification": chosen["classification"],
            "status": chosen["status"], "protocol": chosen["protocol"],
            "content_type": chosen["content_type"], "body_len": chosen["body_len"],
            "body_sha256": chosen["body_sha256"], "body_preview": chosen["body_preview"]}