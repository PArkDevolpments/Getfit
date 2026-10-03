"""Generate the browser-native Getfit UI review ZIP from the current checkout."""

from __future__ import annotations

import argparse
import os
import socket
import tempfile
import threading
import time
from pathlib import Path

import httpx
import uvicorn
from playwright.sync_api import sync_playwright
from sqlalchemy.orm import Session

from hwa.auth.principal import StaticPrincipalProvider
from hwa.db.base import Base
from hwa.db.engine import DatabaseSettings, create_engine
from hwa.main import create_app
from hwa.runtime import build_installation_equipment_profile
from hwa.services.production_bootstrap import (
    ProductionBootstrapConfig,
    bootstrap_production,
)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_until_ready(url: str, timeout_seconds: float = 20.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            response = httpx.get(url, timeout=1.0)
            if response.status_code == 200:
                return
        except Exception as exc:  # pragma: no cover - startup race diagnostics
            last_error = exc
        time.sleep(0.1)
    raise RuntimeError(f"review server did not become ready: {last_error}")


def _build_review_app(database_path: Path):
    root = Path(__file__).resolve().parents[1]
    engine = create_engine(
        DatabaseSettings(database_url=f"sqlite:///{database_path.as_posix()}")
    )
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        bootstrap_production(
            session,
            ProductionBootstrapConfig.from_raw("review-ha-kris", None),
            root / "programme_seed" / "home-workout-12m-v1" / "programme.json",
            root / "programme_seed" / "home-workout-12m-v1" / "week-01.json",
        )

    app = create_app(
        principal_provider=StaticPrincipalProvider("review-ha-kris", "Kris"),
        engine=engine,
        equipment_profile=build_installation_equipment_profile(),
    )
    return app, engine


def generate_review_pack(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    sha = os.getenv("GITHUB_SHA", "local")
    filename = f"getfit-ui-review-{sha[:12]}.zip"
    destination = output_dir / filename

    with tempfile.TemporaryDirectory(prefix="getfit-review-") as temp_dir:
        app, engine = _build_review_app(Path(temp_dir) / "review.db")
        port = _free_port()
        server = uvicorn.Server(
            uvicorn.Config(
                app,
                host="127.0.0.1",
                port=port,
                log_level="warning",
                access_log=False,
            )
        )
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()

        try:
            _wait_until_ready(f"http://127.0.0.1:{port}/healthz")
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                context = browser.new_context(
                    viewport={"width": 1600, "height": 1200},
                    accept_downloads=True,
                )
                page = context.new_page()
                page.goto(
                    f"http://127.0.0.1:{port}/review-capture",
                    wait_until="domcontentloaded",
                    timeout=30000,
                )
                with page.expect_download(timeout=240000) as download_info:
                    page.locator("#run-automated-audit").click()
                download = download_info.value
                download.save_as(destination)
                context.close()
                browser.close()
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            engine.dispose()

    if not destination.exists() or destination.stat().st_size == 0:
        raise RuntimeError("review pack was not generated")
    return destination


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("dist/review-pack"),
    )
    args = parser.parse_args()
    pack = generate_review_pack(args.output_dir)
    print(pack)


if __name__ == "__main__":
    main()
