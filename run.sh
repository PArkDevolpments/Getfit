#!/usr/bin/with-contenv bashio
set -euo pipefail

export HWA_TREADMILL_AVAILABLE="$(bashio::config 'treadmill_available')"
export HWA_TREADMILL_MAX_INCLINE_PERCENT="$(bashio::config 'treadmill_max_incline_percent')"
export HWA_SPIN_BIKE_AVAILABLE="$(bashio::config 'spin_bike_available')"
export HWA_ADJUSTABLE_DUMBBELLS_AVAILABLE="$(bashio::config 'adjustable_dumbbells_available')"

cd /data

alembic -c /app/alembic.ini upgrade head

export HWA_KRIS_HA_USER_ID="$(bashio::config 'kris_ha_user_id')"
export HWA_KIRSTY_HA_USER_ID="$(bashio::config 'kirsty_ha_user_id')"

exec uvicorn hwa.runtime:app \
  --host 0.0.0.0 \
  --port 8099 \
  --no-proxy-headers
