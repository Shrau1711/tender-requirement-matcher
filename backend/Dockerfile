# Backend image. Build from the repository root so the manufacturers' documents (data/categories) are included:
#   docker build -f backend/Dockerfile -t <user>/tender-matcher-backend .
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    FASTEMBED_CACHE_PATH=/opt/fastembed \
    CACHE_DIR=/data/cache \
    RUNS_DIR=/data/runs

WORKDIR /app/backend

COPY backend/requirements.txt .
RUN pip install -r requirements.txt

# The embedding model is downloaded now, so the container works without reaching the internet for it.
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5')"

COPY backend/app app
COPY backend/config config
COPY backend/scripts scripts
COPY data/categories /app/data/categories
# Model answers for the example tenders, so running them costs nothing (see scripts/cost/export_demo_cache.py).
COPY data/demo_cache /app/data/demo_cache

# The vectors of the manufacturers' passages and of the example tenders' questions, as computed where the answers above were saved.
# Searching with the same vectors finds the same passages, so those answers are found; vectors computed on another machine differ in the last digits.
COPY data/seed_embeddings.sqlite /app/data/seed_embeddings.sqlite

# Everything the service writes (stored runs, cached model answers) lives in /data, which can be a volume.
RUN useradd --create-home --uid 10001 app && mkdir -p /data/runs /data/cache && chown -R app /data /opt/fastembed
USER app
VOLUME /data

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
