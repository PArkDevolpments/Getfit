#!/usr/bin/with-contenv bashio
set -euo pipefail

cd /data

alembic -c /app/alembic.ini upgrade head

exec uvicorn hwa.main:app \
  --host 0.0.0.0 \
  --port 8099 \
  --proxy-headers \
  --forwarded-allow-ips "172.30.32.2"
