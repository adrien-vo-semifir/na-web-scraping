# Liste {url, level} pour la passe (niveau constant sur tout le lot).
def main(urls: list, level: str = "http"):
    return [{"url": u, "level": level} for u in (urls or [])]