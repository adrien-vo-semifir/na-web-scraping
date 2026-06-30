# Branche "liste" (défaut) : seeds fournis tels quels.
def main(urls: list = None):
    return {"kind": "list", "urls": urls or []}