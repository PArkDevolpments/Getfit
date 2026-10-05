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
    assert app.version == app_version == "0.1.36"


def test_healthz_reports_service_and_version() -> None:
    _, app = _load_application()
    response = TestClient(app).get("/healthz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "home-workout-assistant",
        "version": "0.1.36",
    }


def test_browser_security_headers_are_applied() -> None:
    _, app = _load_application()
    response = TestClient(app).get("/healthz")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "SAMEORIGIN"
    assert response.headers["referrer-policy"] == "same-origin"
    assert "camera=()" in response.headers["permissions-policy"]
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert "object-src 'none'" in response.headers["content-security-policy"]
