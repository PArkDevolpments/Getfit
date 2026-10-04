from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPONENT = ROOT / "custom_components" / "getfit_panel"


def test_full_canvas_panel_companion_is_packaged_without_broad_app_permissions() -> None:
    manifest = (COMPONENT / "manifest.json").read_text(encoding="utf-8")
    init = (COMPONENT / "__init__.py").read_text(encoding="utf-8")
    app_config = (ROOT / "getfit" / "config.yaml").read_text(encoding="utf-8")

    assert '"domain": "getfit_panel"' in manifest
    assert '"version": "0.1.28"' in manifest
    assert '"config_flow": true' in manifest
    assert '"panel_custom"' in manifest

    assert 'PANEL_URL_PATH = "getfit-full"' in init
    assert 'BUILTIN_PANEL_URL_PATH = "getfit"' in init
    assert "frontend.async_panel_exists(hass, BUILTIN_PANEL_URL_PATH)" in init
    assert "EVENT_PANELS_UPDATED" in init
    assert "handle_safe_area=True" in init
    assert "embed_iframe=False" in init
    assert "require_admin=False" in init

    assert "homeassistant_config" not in app_config
    assert "8099/tcp" not in app_config


def test_full_canvas_panel_uses_normal_supervisor_ingress_without_leaking_hass() -> None:
    panel = (COMPONENT / "frontend" / "getfit_panel.js").read_text(encoding="utf-8")

    assert "endpoint: '/ingress/session'" in panel
    assert "endpoint: `/addons/${slug}/info`" in panel
    assert "endpoint: '/ingress/validate_session'" in panel
    assert "ingress_session=" in panel
    assert "addon.ingress_url" in panel
    assert "getfit-full-canvas-panel" in panel

    # The child gets only the ingress URL and resolved safe-area properties.
    assert "this._frame.hass" not in panel
    assert "access_token" not in panel
    assert "authorization" not in panel.lower()
    assert "home-assistant/properties" in panel
    assert "--safe-area-inset-top" in panel
    assert "--safe-area-inset-bottom" in panel


def test_device_review_records_which_home_assistant_panel_host_is_active() -> None:
    shell = (ROOT / "src" / "hwa" / "web" / "static" / "ha-shell.js").read_text(
        encoding="utf-8"
    )
    review = (
        ROOT / "src" / "hwa" / "web" / "static" / "review-capture.js"
    ).read_text(encoding="utf-8")

    assert "data.host || 'home-assistant-app-panel'" in shell
    assert "ha_panel_host:" in review
    assert "ha_shell_ready:" in review
