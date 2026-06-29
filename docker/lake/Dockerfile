# Image one-shot de provisionnement du lac (bucket + zones), idempotente.
FROM python:3.12-slim
RUN pip install --no-cache-dir boto3
COPY zones.json init_lake.py /lake/
WORKDIR /lake
ENTRYPOINT ["python", "init_lake.py"]
