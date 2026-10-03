"""Application bootstrap for Home Workout Assistant."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Engine

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

APP_VERSION = "0.1.21"
_WEB_DIR = Path(__file__).parent / "web"
_LOCAL_VIDEO_DIR = Path("/media/getfit/videos")


def create_app(
    principal_provider: PrincipalProvider | None = None,
    engine: Engine | None = None,
    pep_health_reader: PepHealthReader | None = None,
    menu_nutrition_reader: MenuNutritionReader | None = None,
    equipment_profile: InstallationEquipmentProfile | None = None,
    pep_bridge_token: str | None = None,
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
    application.add_exception_handler(
        WebIdentitySetupRequired,
        setup_required_exception_handler,
    )
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
