#!/usr/bin/with-contenv bashio
set -euo pipefail

export HWA_TREADMILL_AVAILABLE="$(bashio::config 'treadmill_available')"
export HWA_TREADMILL_MAX_INCLINE_PERCENT="$(bashio::config 'treadmill_max_incline_percent')"
export HWA_SPIN_BIKE_AVAILABLE="$(bashio::config 'spin_bike_available')"
export HWA_ADJUSTABLE_DUMBBELLS_AVAILABLE="$(bashio::config 'adjustable_dumbbells_available')"

cd /data

alembic -c /app/alembic.ini upgrade head

exec uvicorn hwa.runtime:app \
  --host 0.0.0.0 \
  --port 8099 \
  --proxy-headers \
  --forwarded-allow-ips "172.30.32.2"
