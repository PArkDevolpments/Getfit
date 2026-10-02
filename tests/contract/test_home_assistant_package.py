from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_repository_is_installable_as_a_home_assistant_app_repository() -> None:
    repository = ROOT / "repository.yaml"
    app_config = ROOT / "getfit" / "config.yaml"

    assert repository.is_file()
    assert app_config.is_file()
    assert not (ROOT / "config.yaml").exists()

    repository_text = repository.read_text(encoding="utf-8")
    config_text = app_config.read_text(encoding="utf-8")

    assert "name: \"Getfit Home Assistant Apps\"" in repository_text
    assert 'version: "0.1.12"' in config_text
    assert "ingress: true" in config_text
    assert "ingress_port: 8099" in config_text
    assert 'image: "ghcr.io/ktgregson93-collab/getfit"' in config_text
    assert "treadmill_max_incline_percent: 20" in config_text
    assert "spin_bike_available: true" in config_text
    assert "adjustable_dumbbells_available: true" in config_text
    assert 'kris_ha_user_id: ""' in config_text
    assert 'kirsty_ha_user_id: ""' in config_text
    assert "kris_ha_user_id: str" in config_text
    assert "kirsty_ha_user_id: str" in config_text


def test_release_versions_are_aligned_to_0_1_12() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    main_module = (ROOT / "src" / "hwa" / "main.py").read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert 'version = "0.1.12"' in pyproject
    assert 'APP_VERSION = "0.1.12"' in main_module
    assert "ARG BUILD_VERSION=0.1.12" in dockerfile


def test_production_container_keeps_persistent_state_and_exports_bootstrap_options() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    run_script = (ROOT / "run.sh").read_text(encoding="utf-8")

    assert "ghcr.io/home-assistant/base-python:3.12-alpine3.24" in dockerfile
    assert "cd /data" in run_script
    assert "alembic -c /app/alembic.ini upgrade head" in run_script
    assert 'export HWA_KRIS_HA_USER_ID="$(bashio::config \'kris_ha_user_id\')"' in run_script
    assert 'export HWA_KIRSTY_HA_USER_ID="$(bashio::config \'kirsty_ha_user_id\')"' in run_script
    assert "uvicorn hwa.runtime:build_production_app" in run_script
    assert "--factory" in run_script
    assert "--no-proxy-headers" in run_script
    assert "--forwarded-allow-ips" not in run_script
