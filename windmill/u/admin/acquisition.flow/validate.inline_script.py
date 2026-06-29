# Étape 2 — VALIDATE : classification finale -> AcquisitionResult + object_key + trace d'escalade.
MAP = {"success": "SUCCESS", "incomplete_spa": "BLOCKED", "blocked": "BLOCKED",
       "permanent": "PERMANENT", "retryable": "RETRYABLE"}

def main(acq: dict):
    final = MAP.get(acq["final_classification"], "PERMANENT")
    day = acq["observed_at"][:10]
    zone = "raw" if final in ("SUCCESS", "UNCHANGED") else "rejected"
    object_key = f"{zone}/{acq['source']}/{acq['dataset']}/{day}/{acq['acquisition_id']}/response.bin"
    trace = " -> ".join(f"{a['rang']}:{a['classification']}" for a in acq["attempts"])
    return {"acquisition_id": acq["acquisition_id"], "url": acq["url"], "final_state": final,
            "rang_used": acq["rang_used"], "entry": acq["entry"], "ladder": acq["ladder"],
            "escalation": acq["attempts"], "escalation_trace": trace,
            "http": {"status": acq["status"], "protocol": acq["protocol"],
                     "content_type": acq["content_type"], "body_len": acq["body_len"],
                     "body_sha256": acq["body_sha256"]},
            "object_key": object_key, "observed_at": acq["observed_at"],
            "s3_uris": acq.get("s3_uris", [])}