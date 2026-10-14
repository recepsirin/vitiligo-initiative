#!/bin/sh
set -e
PORT="${PORT:-8765}"
# Proxy headers are not trusted here: request.client stays the TCP peer, and the
# app reads X-Forwarded-For / X-Forwarded-Proto itself, only for
# VITILIGO_TRUSTED_PROXY_HOPS proxies counted from the right (entries further
# left are client-controlled). See vitiligo.web.ratelimit and vitiligo.web.proxy.
# Single worker on purpose: per-IP rate-limit state is in-process memory.
exec uvicorn vitiligo.web.app:app \
  --host 0.0.0.0 \
  --port "$PORT" \
  --no-proxy-headers
