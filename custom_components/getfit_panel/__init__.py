"""Getfit full-canvas Home Assistant panel companion."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.start import async_at_started

DOMAIN = "getfit_panel"
PANEL_URL_PATH = "getfit"
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

    frontend.async_remove_panel(hass, PANEL_URL_PATH)
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

    del entry
    frontend_root = Path(__file__).parent / "frontend"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(WEB_ROOT_URL_PATH, str(frontend_root), False)]
    )

    async def register(_hass: HomeAssistant) -> None:
        await _async_register_panel(_hass)

    async_at_started(hass, register)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Remove the companion panel. The built-in app panel returns after HA restart."""

    del entry
    frontend.async_remove_panel(hass, PANEL_URL_PATH)
    return True
