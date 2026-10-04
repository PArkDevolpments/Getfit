# Getfit Full-Canvas Home Assistant Panel

## Why this companion exists

The normal Home Assistant app panel wraps Supervisor Ingress in the built-in app frame. On narrow iPhone views that frame can reserve its own toolbar and safe-area treatment before Getfit renders.

Getfit 0.1.28 includes an optional Home Assistant custom integration that replaces only the sidebar host. The Getfit application itself continues to run as the existing Supervisor app, behind Supervisor Ingress, with the same person-scoped identity boundary and persistent data.

The companion does **not** expose a direct Getfit port, does **not** copy Home Assistant credentials into the browser child, and does **not** request write access to the Home Assistant configuration directory from the Getfit app.

## Package

Copy this directory into Home Assistant:

`custom_components/getfit_panel/`

The resulting Home Assistant path must be:

`/config/custom_components/getfit_panel/`

It contains:

- `__init__.py`
- `config_flow.py`
- `manifest.json`
- `strings.json`
- `translations/en.json`
- `frontend/getfit_panel.js`

## Installation

1. Update the Getfit Home Assistant app to the matching release.
2. Copy `custom_components/getfit_panel` from the exact release into `/config/custom_components/getfit_panel`.
3. Restart Home Assistant Core so the custom integration is discovered.
4. Open **Settings → Devices & services → Add integration**.
5. Search for **Getfit Full-Canvas Panel** and add it.
6. Open **Getfit** from the Home Assistant sidebar.

The companion deliberately registers at the existing `/getfit` panel path after Home Assistant has started. It removes the built-in Getfit app-frame panel in memory and registers the full-canvas panel at the same route.

## What the browser host does

The Home Assistant custom panel:

1. receives the signed-in Home Assistant `hass` object;
2. asks Supervisor for Getfit app information;
3. creates the normal Supervisor Ingress session using Home Assistant's Supervisor WebSocket API;
4. stores only the standard `ingress_session` cookie expected by Home Assistant;
5. loads the Supervisor-provided Getfit `ingress_url` in a full-size iframe;
6. keeps the ingress session alive;
7. forwards resolved Home Assistant safe-area insets to Getfit.

The iframe never receives the raw `hass` object, Home Assistant access tokens or arbitrary Supervisor API capability.

## Verification

After installation:

1. Open Getfit from the sidebar.
2. Confirm the duplicate Home Assistant app toolbar is not present.
3. Confirm the visual canvas reaches the available top and bottom safe areas while controls remain clear of the iPhone gesture areas.
4. Go to **More → Diagnostics → Auto-review this device**.
5. Download the review ZIP.
6. In `device-layout-diagnostics.json`, confirm:
   - `ha_shell_ready` is `true`;
   - `ha_panel_host` is `getfit-full-canvas-panel`;
   - bottom-navigation geometry matches the viewport;
   - no horizontal overflow is reported.
7. Check Bike, Treadmill, HARD and Recovery states: the live prescription grid must be fully visible above the product navigation.

## Rollback

If the companion causes a problem:

1. Remove **Getfit Full-Canvas Panel** from Settings → Devices & services.
2. Restart Home Assistant Core.
3. Home Assistant will register the original Supervisor app panel again.
4. The Getfit app, its SQLite database and workout history are untouched by this rollback.

Do not delete Getfit app data to roll back the panel host.
