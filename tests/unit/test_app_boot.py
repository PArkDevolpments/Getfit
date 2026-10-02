from importlib import import_module
from importlib.util import find_spec

from fastapi.testclient import TestClient


def _load_application():
    spec = find_spec("hwa.main")
    assert spec is not None, "hwa.main must exist"
    module = import_module("hwa.main")
    return module.APP_VERSION, module.app


def test_application_boot_contract() -> None:
    app_version, app = _load_application()

    assert app.title == "Home Workout Assistant"
    assert app.version == app_version == "0.1.20"


def test_healthz_reports_service_and_version() -> None:
    _, app = _load_application()
    response = TestClient(app).get("/healthz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "home-workout-assistant",
        "version": "0.1.20",
    }
