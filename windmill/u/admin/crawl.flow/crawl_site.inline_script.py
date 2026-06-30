import httpx, re
from urllib.parse import urljoin, urlparse
# Branche "site" : mini-crawl profondeur 1 (home -> liens même domaine).
def main(site: str, max_links: int = 5):
    with httpx.Client(follow_redirects=True, timeout=30, headers={"User-Agent": "na-web-scraping/0.1"}) as c:
        html = (c.get(site).text or "")
    host = urlparse(site).hostname or ""
    found = []
    for m in re.findall(r'href=["\']([^"\']+)["\']', html):
        u = urljoin(site, m)
        if u.startswith("http") and urlparse(u).hostname == host and u not in found:
            found.append(u)
    return {"kind": "site", "urls": [site] + found[:max_links]}