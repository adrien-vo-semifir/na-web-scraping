from urllib.parse import urlparse
# Plan : ladder des rangs à tenter (entrée adaptative par domaine).
LADDER = ["http", "curl_cffi", "browser", "stealth"]
KNOWN_PROTECTED = {"datadome.co", "nike.com", "g2.com"}
def main(url: str, source: str = "web", dataset: str = "pages",
         configuration_version: str = "v1", entry_rank: str = "auto", max_rank: str = "stealth"):
    host = (urlparse(url).hostname or "").lower()
    if entry_rank == "auto":
        start = "curl_cffi" if any(host == d or host.endswith("." + d) for d in KNOWN_PROTECTED) else "http"
    else:
        start = entry_rank
    ladder = LADDER[LADDER.index(start): LADDER.index(max_rank) + 1]
    return {"ladder": ladder, "url": url, "source": source, "dataset": dataset,
            "configuration_version": configuration_version}