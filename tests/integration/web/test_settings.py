from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from hwa.auth.principal import StaticPrincipalProvider
from hwa.db.base import Base
from hwa.db.engine import DatabaseSettings, create_engine
from hwa.db.models.identity import ExternalIdentityMapping, Person
from hwa.domain.equipment import (
    EquipmentCapability,
    EquipmentKind,
    InstallationEquipmentProfile,
)
from hwa.main import create_app


def _equipment_profile() -> InstallationEquipmentProfile:
    return InstallationEquipmentProfile(
        equipment=(
            EquipmentCapability(
                kind=EquipmentKind.TREADMILL,
                label="Treadmill",
                available=True,
                supports_speed=True,
                supports_incline=True,
                max_incline_percent=Decimal("20"),
            ),
            EquipmentCapability(
                kind=EquipmentKind.SPIN_BIKE,
                label="Spin bike",
                available=True,
                supports_cadence=True,
                supports_resistance=True,
            ),
            EquipmentCapability(
                kind=EquipmentKind.ADJUSTABLE_DUMBBELLS,
                label="Adjustable dumbbells",
                available=True,
            ),
        )
    )


def _seed_people(session: Session) -> None:
    people = (
        Person(
            id="hwa-kris",
            canonical_key="kris",
            display_name="Kris",
            presentation_profile="male",
            active=True,
        ),
        Person(
            id="hwa-kirsty",
            canonical_key="kirsty",
            display_name="Kirsty",
            presentation_profile="female",
            active=True,
        ),
    )
    session.add_all(people)
    session.flush()
    mappings = {
        "hwa-kris": {
            "HOME_ASSISTANT": "ha-kris",
            "PEP_SITE": "person_a",
            "HEALTH_PROFILE": "kris",
            "MENU_NUTRITION": "person_1",
        },
        "hwa-kirsty": {
            "HOME_ASSISTANT": "ha-kirsty",
            "PEP_SITE": "person_b",
            "HEALTH_PROFILE": "kirsty",
            "MENU_NUTRITION": "person_2",
        },
    }
    for person_id, subjects in mappings.items():
        for authority, subject in subjects.items():
            session.add(
                ExternalIdentityMapping(
                    id=f"{person_id}-{authority}",
                    person_id=person_id,
                    authority=authority,
                    external_subject_id=subject,
                )
            )
    session.commit()


def _client(tmp_path, subject: str, *, integrations_configured: bool = True):
    engine = create_engine(
        DatabaseSettings(database_url=f"sqlite:///{tmp_path / (subject + '-settings.db')}")
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed_people(session)

    marker = object() if integrations_configured else None
    app = create_app(
        principal_provider=StaticPrincipalProvider(subject),
        engine=engine,
        equipment_profile=_equipment_profile(),
        pep_health_reader=marker,
        menu_nutrition_reader=marker,
    )
    return TestClient(app), engine


def test_settings_renders_installation_equipment_and_safe_integration_state(tmp_path) -> None:
    client, engine = _client(tmp_path, "ha-kris")
    try:
        response = client.get("/settings")
        assert response.status_code == 200
        html = response.text
        assert "Settings" in html
        assert "Kris" in html
        assert "Kirsty" not in html
        assert "Treadmill" in html
        assert "Incline up to 20%" in html
        assert "Spin bike" in html
        assert "No incline" in html
        assert "Adjustable dumbbells" in html
        assert "Individual calibration" in html
        assert "approved targets and performed evidence" in html
        assert "Pep Health" in html
        assert "Menu-Nutrition" in html
        assert html.count("Configured") >= 2
        assert "person_a" not in html
        assert "person_1" not in html
        assert "http://" not in html
        assert "token" not in html.lower()
        assert "endpoint" not in html.lower()
    finally:
        client.close()
        engine.dispose()


def test_settings_is_person_scoped_but_equipment_remains_installation_level(tmp_path) -> None:
    client, engine = _client(tmp_path, "ha-kirsty")
    try:
        response = client.get("/settings")
        assert response.status_code == 200
        html = response.text
        assert "Kirsty" in html
        assert "Kris" not in html
        assert "Treadmill" in html
        assert "Spin bike" in html
        assert "person_a" not in html
        assert "person_b" not in html
    finally:
        client.close()
        engine.dispose()


def test_settings_rejects_client_selected_identity(tmp_path) -> None:
    client, engine = _client(tmp_path, "ha-kris")
    try:
        response = client.get("/settings?person_id=hwa-kirsty")
        assert response.status_code == 400
        assert response.json()["detail"] == "IDENTITY_SELECTOR_NOT_ALLOWED"
    finally:
        client.close()
        engine.dispose()


def test_settings_reports_unconfigured_integrations_without_exposing_connection_details(tmp_path) -> None:
    client, engine = _client(tmp_path, "ha-kris", integrations_configured=False)
    try:
        response = client.get("/settings")
        assert response.status_code == 200
        html = response.text
        assert html.count("Not configured") >= 2
        assert "http://" not in html
        assert "token" not in html.lower()
        assert "endpoint" not in html.lower()
    finally:
        client.close()
        engine.dispose()
