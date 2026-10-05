"""Application bootstrap for Home Workout Assistant."""

from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Engine
from starlette.responses import Response

from hwa.api.pep_export import router as pep_export_router
from hwa.api.routes.me import router as me_router
from hwa.api.routes.workouts import router as workouts_router
from hwa.auth.ha_ingress import HomeAssistantIngressPrincipalProvider
from hwa.auth.principal import PrincipalProvider
from hwa.db.engine import create_engine, create_session_factory
from hwa.domain.equipment import InstallationEquipmentProfile
from hwa.integrations.menu.reader import MenuNutritionReader
from hwa.integrations.pep.health_reader import PepHealthReader
from hwa.web.dependencies import WebIdentitySetupRequired
from hwa.web.router import router as product_web_router
from hwa.web.setup import setup_required_exception_handler

APP_VERSION = "0.1.38"
_WEB_DIR = Path(__file__).parent / "web"
_LOCAL_VIDEO_DIR = Path("/media/getfit/videos")


def create_app(
    principal_provider: PrincipalProvider | None = None,
    engine: Engine | None = None,
    pep_health_reader: PepHealthReader | None = None,
    menu_nutrition_reader: MenuNutritionReader | None = None,
    equipment_profile: InstallationEquipmentProfile | None = None,
    pep_bridge_token: str | None = None,
    pep_bridge_allowed_person_ids: frozenset[str] | None = None,
) -> FastAPI:
    """Create the HWA application with explicit injectable trust boundaries."""

    application = FastAPI(title="Home Workout Assistant", version=APP_VERSION)
    database_engine = engine or create_engine()
    application.state.principal_provider = (
        principal_provider or HomeAssistantIngressPrincipalProvider()
    )
    application.state.session_factory = create_session_factory(database_engine)
    application.state.pep_health_reader = pep_health_reader
    application.state.menu_nutrition_reader = menu_nutrition_reader
    application.state.equipment_profile = equipment_profile
    application.state.pep_bridge_token = pep_bridge_token.strip() if pep_bridge_token else None
    application.state.pep_bridge_allowed_person_ids = frozenset(
        pep_bridge_allowed_person_ids or ()
    )
    application.add_exception_handler(
        WebIdentitySetupRequired,
        setup_required_exception_handler,
    )

    @application.middleware("http")
    async def harden_responses(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Apply browser hardening without weakening Home Assistant Ingress."""

        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
        )
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "img-src 'self' data:; "
            "media-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; "
            "connect-src 'self'; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'self'",
        )
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response
    application.mount(
        "/static",
        StaticFiles(directory=str(_WEB_DIR / "static")),
        name="static",
    )
    application.mount(
        "/exercise-videos",
        StaticFiles(directory=str(_LOCAL_VIDEO_DIR), check_dir=False),
        name="exercise-videos",
    )
    application.include_router(me_router)
    application.include_router(pep_export_router)
    application.include_router(workouts_router)
    application.include_router(product_web_router)

    @application.get("/healthz")
    def healthz() -> dict[str, str]:
        """Return a minimal process health response."""

        return {
            "status": "ok",
            "service": "home-workout-assistant",
            "version": APP_VERSION,
        }

    return application


app = create_app()
