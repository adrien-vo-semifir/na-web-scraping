#!/usr/bin/env python3
"""Provisionnement IDEMPOTENT du lac S3 : bucket + zones (déclarées dans zones.json).

Rejouable sans risque (create-if-not-exists + marqueurs de zone écrasés). Attend que
SeaweedFS réponde avant d'agir. Config par environnement :

    S3_ENDPOINT          endpoint S3 (ex. http://seaweedfs:8333)
    S3_BUCKET            bucket cible (défaut : valeur de zones.json, sinon "lake")
    S3_ACCESS_KEY_ID / S3_SECRET_ACCESS_KEY / S3_REGION
    LAKE_CONFIG          chemin du zones.json (défaut /lake/zones.json)
"""
import json
import os
import time

import boto3
from botocore.config import Config

CFG = json.load(open(os.environ.get("LAKE_CONFIG", "/lake/zones.json"), encoding="utf-8"))
BUCKET = os.environ.get("S3_BUCKET") or CFG.get("bucket", "lake")
ENDPOINT = os.environ.get("S3_ENDPOINT", "http://seaweedfs:8333")

s3 = boto3.client(
    "s3", endpoint_url=ENDPOINT,
    aws_access_key_id=os.environ.get("S3_ACCESS_KEY_ID", "any"),
    aws_secret_access_key=os.environ.get("S3_SECRET_ACCESS_KEY", "any"),
    region_name=os.environ.get("S3_REGION", "us-east-1"),
    config=Config(s3={"addressing_style": "path"}, retries={"max_attempts": 1}),
)

# 1. Attendre que SeaweedFS soit prêt (le service démarre en parallèle).
for i in range(30):
    try:
        s3.list_buckets()
        break
    except Exception:
        print("attente de SeaweedFS (%s)…" % ENDPOINT, flush=True)
        time.sleep(2)
else:
    raise SystemExit("SeaweedFS injoignable : " + ENDPOINT)

# 2. Bucket (idempotent).
try:
    s3.create_bucket(Bucket=BUCKET)
    print("bucket '%s' créé" % BUCKET)
except Exception as e:
    print("bucket '%s' : %s (déjà présent ?)" % (BUCKET, type(e).__name__))

# 3. Marqueurs de zone (idempotent : on écrase _zone.json). Rend le lac auto-documenté.
for zone, desc in CFG["zones"].items():
    s3.put_object(
        Bucket=BUCKET, Key="%s/_zone.json" % zone,
        Body=json.dumps({"zone": zone, "description": desc}, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )
    print("  zone %-9s -> %s/_zone.json" % (zone, zone))

print("Lac provisionné : %s | zones : %s" % (BUCKET, ", ".join(CFG["zones"])))
