#!/bin/sh
set -e
PORT="${PORT:-8765}"
exec uvicorn vitiligo.web.app:app \
  --host 0.0.0.0 \
  --port "$PORT" \
  --proxy-headers \
  --forwarded-allow-ips='*'
