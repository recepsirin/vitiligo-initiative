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

# And the corpus, for hosts with no persistent volume. A mounted volume at /data
# still wins, because it is mounted over this layer, so baking it in costs
# nothing where a volume exists. SQLite needs to write a WAL beside the file and
# the migration in init_db() adds columns; both happen in the container's own
# writable layer and are discarded on restart, which is harmless because they
# are reproduced identically on the next start.
# The glob may match nothing — on a host that builds from a git clone the corpus
# is not there, because data/ is gitignored and the file is far over GitHub's
# 100 MB limit. Pairing it with a file that always exists keeps the build working
# either way: baked where the corpus is present, supplied by a volume where it is not.
COPY .dockerignore data/vitiligo.db* /data/

EXPOSE 8765

ENTRYPOINT ["/entrypoint.sh"]
