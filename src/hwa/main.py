"""Application bootstrap for Home Workout Assistant."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Engine

from hwa.api.routes.me import router as me_router
from hwa.api.routes.workouts import router as workouts_router
from hwa.auth.ha_ingress import HomeAssistantIngressPrincipalProvider
from hwa.auth.principal import PrincipalProvider
from hwa.db.engine import create_engine, create_session_factory
from hwa.web.router import router as product_web_router

APP_VERSION = "0.1.0"
_WEB_DIR = Path(__file__).parent / "web"


def create_app(
    principal_provider: PrincipalProvider | None = None,
    engine: Engine | None = None,
) -> FastAPI:
    """Create the HWA application with explicit injectable trust boundaries."""

    application = FastAPI(title="Home Workout Assistant", version=APP_VERSION)
    database_engine = engine or create_engine()
    application.state.principal_provider = (
        principal_provider or HomeAssistantIngressPrincipalProvider()
    )
    application.state.session_factory = create_session_factory(database_engine)
    application.mount(
        "/static",
        StaticFiles(directory=str(_WEB_DIR / "static")),
        name="static",
    )
    application.include_router(me_router)
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
