from pathlib import Path

from fastapi import Request

from hwa.web.urls import ingress_prefix, ingress_url

ROOT = Path(__file__).resolve().parents[2]


def _request(path: str = "/", ingress_path: str | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if ingress_path is not None:
        headers.append((b"x-ingress-path", ingress_path.encode("ascii")))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "headers": headers,
        "client": ("127.0.0.1", 1234),
        "server": ("testserver", 80),
    }
    return Request(scope)


def test_ingress_url_prefixes_assets_routes_and_api_paths() -> None:
    request = _request(ingress_path="/api/hassio_ingress/abcDEF_123-token")

    assert ingress_prefix(request) == "/api/hassio_ingress/abcDEF_123-token"
    assert ingress_url(request, "/static/app.css") == (
        "/api/hassio_ingress/abcDEF_123-token/static/app.css"
    )
    assert ingress_url(request, "/workout") == "/api/hassio_ingress/abcDEF_123-token/workout"
    assert ingress_url(request, "/api/v1/workouts/drafts") == (
        "/api/hassio_ingress/abcDEF_123-token/api/v1/workouts/drafts"
    )


def test_direct_requests_keep_root_relative_application_paths() -> None:
    request = _request()

    assert ingress_prefix(request) == ""
    assert ingress_url(request, "/static/app.css") == "/static/app.css"
    assert ingress_url(request, "/") == "/"


def test_ingress_prefix_rejects_non_supervisor_path_shapes() -> None:
    assert ingress_prefix(_request(ingress_path="//evil.example")) == ""
    assert ingress_prefix(_request(ingress_path="javascript:alert(1)")) == ""
    assert ingress_prefix(_request(ingress_path="/api/hassio_ingress/token/extra")) == ""


def test_templates_do_not_hardcode_root_absolute_assets_or_navigation() -> None:
    template_dir = ROOT / "src/hwa/web/templates"
    templates = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(template_dir.glob("*.html"))
    )

    assert 'href="/static/' not in templates
    assert 'src="/static/' not in templates
    assert "fetch('/api/" not in templates
    assert 'href="/library' not in templates
