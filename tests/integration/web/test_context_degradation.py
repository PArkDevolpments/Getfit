from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from hwa.auth.principal import StaticPrincipalProvider
from hwa.db.base import Base
from hwa.db.engine import DatabaseSettings, create_engine
from hwa.db.models.identity import ExternalIdentityMapping, Person
from hwa.db.models.programme import ProgrammeDay, ProgrammeDefinition
from hwa.integrations.menu.reader import MacroTargets, MenuNutritionContext
from hwa.integrations.pep.health_reader import PepHealthContext, PepHealthMetric
from hwa.main import create_app


def _metric(metric: str, value: float, unit: str) -> PepHealthMetric:
    return PepHealthMetric(
        status="available",
        metric=metric,
        value=value,
        unit=unit,
        recorded_at="2026-10-01T06:30:00Z",
        derived=False,
        reason="OK",
    )


class FakePepReader:
    def __init__(self, context: PepHealthContext) -> None:
        self.context = context

    async def read(self, person) -> PepHealthContext:
        assert person.pep_person_id == "person_a"
        assert person.health_profile_id == "kris"
        return self.context


class FakeMenuReader:
    def __init__(self, context: MenuNutritionContext) -> None:
        self.context = context

    async def read(self, person, *, start=None, end=None) -> MenuNutritionContext:
        del start, end
        assert person.menu_person_id == "person_1"
        return self.context


def _client(tmp_path, pep: PepHealthContext, menu: MenuNutritionContext):
    engine = create_engine(DatabaseSettings(database_url=f"sqlite:///{tmp_path / 'context.db'}"))
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            Person(
                id="hwa-kris",
                canonical_key="kris",
                display_name="Kris",
                presentation_profile="male",
                active=True,
            )
        )
        session.flush()
        for authority, subject in {
            "HOME_ASSISTANT": "ha-kris",
            "PEP_SITE": "person_a",
            "HEALTH_PROFILE": "kris",
            "MENU_NUTRITION": "person_1",
        }.items():
            session.add(
                ExternalIdentityMapping(
                    id=f"hwa-kris-{authority}",
                    person_id="hwa-kris",
                    authority=authority,
                    external_subject_id=subject,
                )
            )
        session.add(
            ProgrammeDefinition(
                programme_id="home-workout-12m-v1",
                schema_version=1,
                title="Home Workout",
                active=True,
                seed_checksum="seed",
            )
        )
        session.flush()
        session.add(
            ProgrammeDay(
                id="week1-day1",
                programme_id="home-workout-12m-v1",
                week_number=1,
                day_number=1,
                title="Upper Body + Bike",
                workout_type="upper_body_bike",
                block="foundation",
            )
        )
        session.commit()

    app = create_app(
        principal_provider=StaticPrincipalProvider("ha-kris"),
        engine=engine,
        pep_health_reader=FakePepReader(pep),
        menu_nutrition_reader=FakeMenuReader(menu),
    )
    return TestClient(app), engine


def _ready_pep() -> PepHealthContext:
    return PepHealthContext(
        status="READY",
        reason="OK",
        pep_person_id="person_a",
        health_profile_id="kris",
        data_quality="GOOD",
        body={"body_mass": _metric("body_mass", 113.7, "kg")},
        sleep={"sleep_duration": _metric("sleep_duration", 7.2, "h")},
    )


def _ready_menu() -> MenuNutritionContext:
    return MenuNutritionContext(
        status="READY",
        reason="OK",
        menu_person_id="person_1",
        current_target=MacroTargets(
            calories_kcal=2150,
            protein_g=180,
            carbohydrate_g=190,
            fat_g=70,
        ),
    )


def test_today_renders_read_only_health_and_nutrition_context(tmp_path) -> None:
    client, engine = _client(tmp_path, _ready_pep(), _ready_menu())
    try:
        response = client.get("/")
        assert response.status_code == 200
        html = response.text
        assert "Health context" in html
        assert "113.7 kg" in html
        assert "7.2 h sleep" in html
        assert "Nutrition context" in html
        assert "2150 kcal target" in html
        assert 'data-primary-action="start"' in html
        assert "person_a" not in html
        assert "person_1" not in html
    finally:
        client.close()
        engine.dispose()


def test_today_keeps_workout_available_when_both_context_sources_are_unavailable(tmp_path) -> None:
    pep = PepHealthContext(
        status="UNAVAILABLE",
        reason="DATASET_STALE",
        pep_person_id="person_a",
    )
    menu = MenuNutritionContext(
        status="UNAVAILABLE",
        reason="MENU_NUTRITION_UNAVAILABLE",
        menu_person_id="person_1",
    )
    client, engine = _client(tmp_path, pep, menu)
    try:
        response = client.get("/")
        assert response.status_code == 200
        html = response.text
        assert 'data-primary-action="start"' in html
        assert "Health context unavailable" in html
        assert "Nutrition context unavailable" in html
        assert "DATASET_STALE" not in html
        assert "MENU_NUTRITION_UNAVAILABLE" not in html
    finally:
        client.close()
        engine.dispose()


def test_default_app_degrades_without_configured_external_readers(tmp_path) -> None:
    engine = create_engine(DatabaseSettings(database_url=f"sqlite:///{tmp_path / 'default.db'}"))
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            Person(
                id="hwa-kris",
                canonical_key="kris",
                display_name="Kris",
                presentation_profile="male",
                active=True,
            )
        )
        session.flush()
        for authority, subject in {
            "HOME_ASSISTANT": "ha-kris",
            "PEP_SITE": "person_a",
            "HEALTH_PROFILE": "kris",
            "MENU_NUTRITION": "person_1",
        }.items():
            session.add(
                ExternalIdentityMapping(
                    id=f"default-{authority}",
                    person_id="hwa-kris",
                    authority=authority,
                    external_subject_id=subject,
                )
            )
        session.commit()
    client = TestClient(create_app(principal_provider=StaticPrincipalProvider("ha-kris"), engine=engine))
    try:
        response = client.get("/")
        assert response.status_code == 200
        assert "Health context unavailable" in response.text
        assert "Nutrition context unavailable" in response.text
    finally:
        client.close()
        engine.dispose()
