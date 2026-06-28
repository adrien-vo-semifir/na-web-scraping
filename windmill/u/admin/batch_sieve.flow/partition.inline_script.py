# Partition du lot après la passe : succès vs échec (match par URL, fallback index).
OK = {"SUCCESS", "UNCHANGED"}
def main(urls: list, results: list, category: str = "default", level: str = "http"):
    by_url = {}
    for r in (results or []):
        if isinstance(r, dict) and r.get("url"):
            by_url[r["url"]] = r
    ok, fail = [], []
    for i, url in enumerate(urls or []):
        r = by_url.get(url)
        if r is None and results and i < len(results) and isinstance(results[i], dict):
            r = results[i]
        st = r.get("final_state") if isinstance(r, dict) else None
        rg = r.get("rang_used") if isinstance(r, dict) else None
        (ok if st in OK else fail).append({"url": url, "final_state": st or "ERROR", "rang": rg})
    return {"category": category, "level": level, "n_total": len(urls or []),
            "n_ok": len(ok), "n_fail": len(fail),
            "ok_urls": [o["url"] for o in ok], "fail_urls": [f["url"] for f in fail],
            "ok": ok, "fail": fail}