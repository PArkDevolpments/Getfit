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
    assert "ingress: true" in config_text
    assert "ingress_port: 8099" in config_text
    assert 'image: "ghcr.io/ktgregson93-collab/getfit"' in config_text
    assert "treadmill_max_incline_percent: 20" in config_text
    assert "spin_bike_available: true" in config_text
    assert "adjustable_dumbbells_available: true" in config_text


def test_production_container_keeps_persistent_state_in_data_and_runs_migrations() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    run_script = (ROOT / "run.sh").read_text(encoding="utf-8")

    assert "ghcr.io/home-assistant/base-python:3.12-alpine3.24" in dockerfile
    assert "cd /data" in run_script
    assert "alembic -c /app/alembic.ini upgrade head" in run_script
    assert "uvicorn hwa.runtime:app" in run_script
    assert 'forwarded-allow-ips "172.30.32.2"' in run_script
