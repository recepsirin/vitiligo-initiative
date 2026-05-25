FROM python:3.13-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends libxml2 libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY scripts/docker-entrypoint.sh /entrypoint.sh

RUN pip install --no-cache-dir . \
    && chmod +x /entrypoint.sh

ENV VITILIGO_WEB_HOST=0.0.0.0 \
    VITILIGO_DB_PATH=/data/vitiligo.db \
    FASTEMBED_CACHE_PATH=/data/cache \
    VITILIGO_PREWARM_EMBEDDINGS=1 \
    PYTHONUNBUFFERED=1

# Bake the ONNX embedding model into the image (~80 MB).
RUN mkdir -p /data/cache \
    && python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5')"

EXPOSE 8765

ENTRYPOINT ["/entrypoint.sh"]
