import httpx, re
from urllib.parse import urljoin, urlparse

# Étape conditionnelle : un SITE (mini-crawl profondeur 1, liens même domaine) OU une LISTE de seeds.
def main(kind: str = "list", site: str = "", urls: list = None, max_links: int = 5):
    if kind == "site" and site:
        with httpx.Client(follow_redirects=True, timeout=30,
                          headers={"User-Agent": "na-web-scraping/0.1 (+acquisition; POC)"}) as c:
            html = (c.get(site).text or "")
        host = urlparse(site).hostname or ""
        found = []
        for m in re.findall(r'href=["\']([^"\']+)["\']', html):
            u = urljoin(site, m)
            if u.startswith("http") and urlparse(u).hostname == host and u not in found:
                found.append(u)
        return {"kind": "site", "seed": site, "urls": [site] + found[:max_links]}
    return {"kind": "list", "seed": None, "urls": urls or []}