"""Getfit full-canvas Home Assistant panel companion."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_PANELS_UPDATED
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.start import async_at_started

DOMAIN = "getfit_panel"
PANEL_URL_PATH = "getfit-full"
BUILTIN_PANEL_URL_PATH = "getfit"
PANEL_ELEMENT = "getfit-full-canvas-panel"
WEB_ROOT_URL_PATH = "/getfit-panel-static"
PANEL_MODULE_URL = f"{WEB_ROOT_URL_PATH}/getfit_panel.js"
ADDON_SLUG = "getfit"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the integration package."""
    del config
    return True


async def _async_register_panel(hass: HomeAssistant) -> None:
    """Replace any prior companion panel with the full-canvas Getfit host."""

    frontend.async_remove_panel(hass, PANEL_URL_PATH, warn_if_unknown=False)
    await panel_custom.async_register_panel(
        hass=hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name=PANEL_ELEMENT,
        sidebar_title="Getfit",
        sidebar_icon="mdi:dumbbell",
        module_url=PANEL_MODULE_URL,
        embed_iframe=False,
        require_admin=False,
        handle_safe_area=True,
        config={"addon_slug": ADDON_SLUG},
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Register the trusted full-canvas panel after Home Assistant startup."""

    runtime = hass.data.setdefault(DOMAIN, {})
    if not runtime.get("static_registered"):
        frontend_root = Path(__file__).parent / "frontend"
        await hass.http.async_register_static_paths(
            [StaticPathConfig(WEB_ROOT_URL_PATH, str(frontend_root), False)]
        )
        runtime["static_registered"] = True

    entry_runtime: dict[str, object] = {}
    runtime[entry.entry_id] = entry_runtime

    @callback
    def suppress_builtin_panel(_event: object | None = None) -> None:
        if frontend.async_panel_exists(hass, BUILTIN_PANEL_URL_PATH):
            frontend.async_remove_panel(
                hass,
                BUILTIN_PANEL_URL_PATH,
                warn_if_unknown=False,
            )

    async def register(_hass: HomeAssistant) -> None:
        suppress_builtin_panel()
        await _async_register_panel(_hass)
        entry_runtime["unsubscribe_panels"] = _hass.bus.async_listen(
            EVENT_PANELS_UPDATED,
            suppress_builtin_panel,
        )

    entry_runtime["cancel_start"] = async_at_started(hass, register)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Remove the companion panel. The built-in app panel returns after HA restart."""

    runtime = hass.data.get(DOMAIN, {})
    entry_runtime = runtime.pop(entry.entry_id, {})
    if isinstance(entry_runtime, dict):
        for key in ("cancel_start", "unsubscribe_panels"):
            cancel = entry_runtime.get(key)
            if callable(cancel):
                cancel()
    frontend.async_remove_panel(hass, PANEL_URL_PATH, warn_if_unknown=False)
    return True
