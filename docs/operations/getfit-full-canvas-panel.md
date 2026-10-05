# Getfit Full-Canvas Home Assistant Host

## Current supported path

Home Assistant's native app panel now supports the exact full-canvas protocol Getfit needs:

- an app can subscribe with `home-assistant/subscribe-properties`;
- `handleSafeArea: true` tells Home Assistant to remove iframe safe-area padding and forward the resolved inset values;
- `kioskMode: true` lets a narrow app ask Home Assistant to remove the app header while the app is open.

Getfit 0.1.33 uses that native protocol first. On a supported Home Assistant frontend, **no separate Getfit panel integration is required**.

The Getfit child remains behind normal Supervisor Ingress. No Home Assistant access token, raw `hass` object, websocket connection, or direct app port is exposed to Getfit.

## Runtime handshake

Every Getfit page loaded inside Home Assistant runs `ha-shell.js`.

On narrow screens it requests:

```text
home-assistant/subscribe-properties
handleSafeArea = true
kioskMode = true
```

The request is retried for a short bounded period so mobile navigation cannot lose the initial handshake during iframe/panel startup.

When Home Assistant replies with `home-assistant/properties`, Getfit:

1. records the native host as `home-assistant-app-panel`;
2. applies the resolved safe-area insets to its own CSS variables;
3. marks the shell handshake ready;
4. allows the Home Assistant app panel to provide the full available canvas.

The native Home Assistant parent continues to own Supervisor ingress sessions and authentication.

## Device verification

Go to **More → Diagnostics → Auto-review this device**.

The device review now waits for the **outer Home Assistant shell handshake before measuring the viewport**. It records the outer host rather than the nested review iframes.

A valid native full-canvas result should show:

- `home_assistant_shell.ready: true` in `review-manifest.json`;
- `ha_shell_ready: true` in `device-layout-diagnostics.json`;
- `ha_panel_host: "home-assistant-app-panel"` (native host), or `"getfit-full-canvas-panel"` if the legacy companion is used;
- safe-area values from Home Assistant;
- the measured device viewport after the host has applied kiosk/safe-area handling.

If no parent acknowledgement arrives, the review reports `HOME_ASSISTANT_FULL_CANVAS_HANDSHAKE_MISSING` instead of silently passing.

## Legacy companion fallback

The packaged `custom_components/getfit_panel/` integration remains available as a fallback for installations where the native app-panel protocol is unavailable or broken.

It registers `/getfit-full`, obtains the normal Supervisor ingress URL/session in the trusted parent, and hosts Getfit without passing Home Assistant credentials into the child.

Do **not** install the companion merely to work around Getfit layout sizing on a Home Assistant version that supports the native protocol. The native app panel is preferred because it avoids an additional custom integration lifecycle.

## Companion installation (fallback only)

1. Copy `custom_components/getfit_panel/` into:
   `/config/custom_components/getfit_panel/`
2. Restart Home Assistant Core.
3. Open **Settings → Devices & services → Add integration**.
4. Add **Getfit Full-Canvas Panel**.
5. Open Getfit and rerun the device review.

## Rollback

Native path: no installation rollback is needed; removing/updating Getfit removes the child-side request.

Companion fallback: remove **Getfit Full-Canvas Panel** from Devices & services and restart Home Assistant Core. The normal Supervisor app panel returns. Getfit data is not touched.
