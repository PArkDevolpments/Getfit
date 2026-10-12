#!/usr/bin/with-contenv bashio
set +x
set -euo pipefail
umask 077

export HWA_TREADMILL_AVAILABLE="$(bashio::config 'treadmill_available')"
export HWA_TREADMILL_MAX_INCLINE_PERCENT="$(bashio::config 'treadmill_max_incline_percent')"
export HWA_SPIN_BIKE_AVAILABLE="$(bashio::config 'spin_bike_available')"
export HWA_ADJUSTABLE_DUMBBELLS_AVAILABLE="$(bashio::config 'adjustable_dumbbells_available')"

cd /data

alembic -c /app/alembic.ini upgrade head

export HWA_KRIS_HA_USER_ID="$(bashio::config 'kris_ha_user_id')"
export HWA_KIRSTY_HA_USER_ID="$(bashio::config 'kirsty_ha_user_id')"
export HWA_PEP_BRIDGE_TOKEN="$(bashio::config 'pep_bridge_token')"
export HWA_PEP_BRIDGE_ALLOW_PERSON_A="$(bashio::config 'pep_bridge_allow_person_a')"
export HWA_PEP_BRIDGE_ALLOW_PERSON_B="$(bashio::config 'pep_bridge_allow_person_b')"

export HWA_PEP_HEALTH_ENABLED="$(bashio::config 'pep_health_enabled')"
export HWA_PEP_HEALTH_SIGNING_KID="$(bashio::config 'pep_health_signing_kid')"
unset HWA_PEP_HEALTH_SIGNING_KEY_FILE HWA_PEP_HEALTH_SIGNING_PRIVATE_KEY
if [ "$HWA_PEP_HEALTH_ENABLED" = "true" ]; then
  # Write through a new owner-only file, never through an existing key-path symlink.
  # On failure leave the path unset so Python disables Health while serving workouts.
  if health_key_tmp="$(mktemp /data/.pep-health-signing.XXXXXX 2>/dev/null)"; then
    if bashio::config 'pep_health_signing_private_key' > "$health_key_tmp" 2>/dev/null \
      && chmod 600 "$health_key_tmp" 2>/dev/null \
      && mv -fT "$health_key_tmp" /data/pep-health-signing.key 2>/dev/null; then
      export HWA_PEP_HEALTH_SIGNING_KEY_FILE=/data/pep-health-signing.key
    else
      rm -f -- "$health_key_tmp" 2>/dev/null || true
    fi
    unset health_key_tmp
  fi
fi

exec uvicorn hwa.runtime:build_production_app \
  --factory \
  --host 0.0.0.0 \
  --port 8099 \
  --no-proxy-headers
