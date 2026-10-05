"""Generate the browser-native Getfit UI review ZIP from the current checkout."""

from __future__ import annotations

import argparse
import base64
import json
import os
import socket
import tempfile
import threading
import time
import zipfile
from pathlib import Path
from typing import Any

import httpx
import uvicorn
from playwright.sync_api import BrowserContext, sync_playwright
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

_AI_PNG_PROFILES = frozenset({"ha-phone", "desktop"})


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


def _rasterise_svg(
    context: BrowserContext,
    svg_bytes: bytes,
    *,
    width: int,
    height: int,
) -> bytes:
    encoded = base64.b64encode(svg_bytes).decode("ascii")
    viewport_height = min(max(height, 568), 1200)
    page = context.new_page()
    try:
        page.set_viewport_size({"width": width, "height": viewport_height})
        page.set_content(
            (
                "<!doctype html><html><head><style>"
                "html,body{margin:0;padding:0;overflow:hidden;background:#061321}"
                "img{display:block}"
                "</style></head><body>"
                f'<img id="capture" width="{width}" height="{height}" '
                f'src="data:image/svg+xml;base64,{encoded}">'
                "</body></html>"
            ),
            wait_until="load",
        )
        page.locator("#capture").wait_for(state="visible")
        return page.screenshot(
            type="png",
            full_page=True,
            animations="disabled",
        )
    finally:
        page.close()


def _ai_gallery(captures: list[dict[str, Any]]) -> str:
    cards: list[str] = []
    for capture in captures:
        png_file = capture.get("ai_png_file")
        if not png_file:
            continue
        cards.extend(
            [
                '<article class="capture-card">',
                (
                    f"<h2>{capture.get('page_label', capture.get('page', 'Screen'))} · "
                    f"{capture.get('profile_label', capture.get('profile', 'Viewport'))}</h2>"
                ),
                (
                    f"<p>{capture.get('width', '?')} × {capture.get('height', '?')} · "
                    f"{capture.get('page_state', 'unknown')}</p>"
                ),
                (
                    f'<img src="{png_file}" alt="'
                    f"{capture.get('page_label', capture.get('page', 'Screen'))} "
                    'review screenshot">'
                ),
                "</article>",
            ]
        )

    return "".join(
        [
            '<!doctype html><html lang="en-GB"><head><meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width,initial-scale=1">',
            "<title>Getfit AI Review Gallery</title><style>",
            "body{margin:0;padding:24px;background:#061321;color:#eaf6ff;"
            "font-family:system-ui,sans-serif}",
            "main{max-width:1440px;margin:auto;display:grid;gap:20px}",
            ".capture-card{padding:14px;border:1px solid #21415a;border-radius:16px;"
            "background:#0a2033}",
            ".capture-card h2{margin:0;font-size:16px}.capture-card p{color:#9eb8ca}",
            ".capture-card img{display:block;max-width:100%;height:auto;"
            "border-radius:10px;background:#fff}",
            "</style></head><body><h1>Getfit AI Review Gallery</h1><main>",
            "".join(cards),
            "</main></body></html>",
        ]
    )


def _enrich_pack_for_ai(pack_path: Path, context: BrowserContext) -> None:
    with zipfile.ZipFile(pack_path, "r") as source:
        entries = {name: source.read(name) for name in source.namelist()}

    manifest_raw = entries.get("review-manifest.json")
    if manifest_raw is None:
        raise RuntimeError("review pack is missing review-manifest.json")

    manifest = json.loads(manifest_raw.decode("utf-8"))
    captures = manifest.get("captures")
    if not isinstance(captures, list):
        raise RuntimeError("review manifest does not contain a capture list")

    selected = [
        capture
        for capture in captures
        if isinstance(capture, dict)
        and capture.get("profile") in _AI_PNG_PROFILES
        and str(capture.get("file", "")).endswith(".svg")
    ]
    if not selected:
        selected = [
            capture
            for capture in captures
            if isinstance(capture, dict)
            and capture.get("capture_kind") == "viewport"
            and str(capture.get("file", "")).endswith(".svg")
        ]

    png_count = 0
    for capture in selected:
        svg_name = str(capture["file"])
        svg_bytes = entries.get(svg_name)
        if svg_bytes is None:
            raise RuntimeError(f"review SVG is missing from pack: {svg_name}")

        width = int(capture.get("width") or 1)
        height = int(capture.get("height") or 1)
        png_name = f"ai-screenshots/{Path(svg_name).stem}.png"
        entries[png_name] = _rasterise_svg(
            context,
            svg_bytes,
            width=width,
            height=height,
        )
        capture["ai_png_file"] = png_name
        png_count += 1

    manifest["ai_review"] = {
        "format": "getfit-ai-review-assets-v1",
        "png_profiles": sorted(_AI_PNG_PROFILES),
        "png_count": png_count,
        "content_index": "review-content.json",
        "gallery": "ai-review-gallery.html",
        "vector_source_complete": True,
    }
    entries["review-manifest.json"] = json.dumps(
        manifest,
        indent=2,
        ensure_ascii=False,
    ).encode("utf-8")
    entries["ai-review-gallery.html"] = _ai_gallery(captures).encode("utf-8")
    entries["AI-REVIEW-GUIDE.txt"] = (
        b"Getfit AI Review Guide\n\n"
        b"Read review-content.json first for rendered text, headings and controls. "
        b"Inspect ai-screenshots/*.png for actual browser-rendered visual evidence at the "
        b"Home Assistant phone and desktop extremes. The SVG files are complete lossless "
        b"backing evidence; some text-only extractors truncate large SVG source inside the "
        b"embedded CSS, so that truncation must not be treated as a broken Getfit export.\n"
    )

    replacement = pack_path.with_suffix(".repacked.zip")
    with zipfile.ZipFile(
        replacement,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=6,
    ) as target:
        for name, data in entries.items():
            target.writestr(name, data)

    replacement.replace(pack_path)


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
                _enrich_pack_for_ai(destination, context)
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
