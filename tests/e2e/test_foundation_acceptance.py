from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from hwa.auth.principal import StaticPrincipalProvider
from hwa.db.base import Base
from hwa.db.engine import DatabaseSettings, create_engine
from hwa.db.models.identity import ExternalIdentityMapping, Person
from hwa.db.models.programme import ProgrammeDay
from hwa.db.models.workout import WorkoutRevision
from hwa.domain.identity import PersonContext
from hwa.integrations.menu.reader import MenuNutritionReader
from hwa.integrations.pep.health_reader import PepHealthReader
from hwa.integrations.pep.workout_projection import project_workout_for_pep
from hwa.main import create_app
from hwa.services.programmes import import_week_seed
from hwa.services.workout_evidence import get_effective_workout

PROGRAMME_MANIFEST = Path("programme_seed/home-workout-12m-v1/programme.json")
WEEK_ONE = Path("programme_seed/home-workout-12m-v1/week-01.json")


def _seed_identity(session: Session) -> None:
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
    for person_id, authorities in mappings.items():
        for authority, external_id in authorities.items():
            session.add(
                ExternalIdentityMapping(
                    id=f"{person_id}-{authority}",
                    person_id=person_id,
                    authority=authority,
                    external_subject_id=external_id,
                )
            )
    session.commit()


def _event_payload(session_rpe: int = 6) -> dict[str, object]:
    start = datetime(2026, 10, 1, 7, 0, tzinfo=UTC)
    end = start + timedelta(minutes=42)
    return {
        "event_id": "foundation-acceptance-event",
        "source_event_id": "foundation-acceptance-event",
        "start_at": start.isoformat(),
        "end_at": end.isoformat(),
        "duration_seconds": 2520,
        "workout_type": "upper_body_bike",
        "programme": {
            "programme_id": "home-workout-12m-v1",
            "programme_week": 1,
            "programme_day": 1,
            "block": "foundation",
        },
        "effort": {"session_rpe": session_rpe},
        "heart_rate_response": {"status": "UNAVAILABLE"},
        "training_load": {"status": "UNAVAILABLE"},
        "performance": {"completed": True, "strength": [], "cardio": []},
        "provenance": {
            "authority": "HOME_WORKOUT_ASSISTANT",
            "source_instance": "home-workout-assistant",
            "recorded_at": end.isoformat(),
        },
    }


def _context() -> PersonContext:
    return PersonContext(
        hwa_person_id="hwa-kris",
        pep_person_id="person_a",
        health_profile_id="kris",
        menu_person_id="person_1",
        presentation_profile="male",
        display_name="Kris",
    )


def test_foundation_full_training_evidence_journey_survives_restart(tmp_path) -> None:
    database_path = tmp_path / "foundation-acceptance.db"
    settings = DatabaseSettings(database_url=f"sqlite:///{database_path}")
    engine = create_engine(settings)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed_identity(session)
        imported = import_week_seed(session, PROGRAMME_MANIFEST, WEEK_ONE)
        assert imported.changed is True
        assert imported.day_count == 4
        day_one = session.scalar(
            select(ProgrammeDay).where(
                ProgrammeDay.programme_id == "home-workout-12m-v1",
                ProgrammeDay.week_number == 1,
                ProgrammeDay.day_number == 1,
            )
        )
        assert day_one is not None
        day_one_id = day_one.id

    first_client = TestClient(
        create_app(principal_provider=StaticPrincipalProvider("ha-kris"), engine=engine)
    )
    try:
        me = first_client.get("/api/v1/me")
        assert me.status_code == 200
        assert me.json()["hwa_person_id"] == "hwa-kris"
        assert me.json()["pep_person_id"] == "person_a"

        home = first_client.get("/")
        assert home.status_code == 200
        assert 'data-primary-action="start"' in home.text
        assert day_one_id in home.text

        created = first_client.post(
            "/api/v1/workouts/drafts",
            json={
                "programme_day_id": day_one_id,
                "snapshot": {"phase": "WORKOUT_READY", "state_data": {}},
                "started_at": "2026-10-01T07:00:00Z",
            },
        )
        assert created.status_code == 201
        draft = created.json()

        autosaved = first_client.put(
            f"/api/v1/workouts/drafts/{draft['draft_id']}",
            json={
                "expected_version": draft["version"],
                "snapshot": {
                    "phase": "ACTIVE_SET",
                    "state_data": {"exercise_id": "dumbbell_floor_press", "set": 1},
                },
                "saved_at": "2026-10-01T07:12:00Z",
            },
        )
        assert autosaved.status_code == 200
        assert autosaved.json()["version"] == 2
    finally:
        first_client.close()
        engine.dispose()

    restarted_engine = create_engine(settings)
    kris = TestClient(
        create_app(
            principal_provider=StaticPrincipalProvider("ha-kris"),
            engine=restarted_engine,
        )
    )
    kirsty = TestClient(
        create_app(
            principal_provider=StaticPrincipalProvider("ha-kirsty"),
            engine=restarted_engine,
        )
    )
    try:
        resumed_page = kris.get("/")
        assert resumed_page.status_code == 200
        assert 'data-primary-action="resume"' in resumed_page.text
        assert draft["draft_id"] in resumed_page.text

        active = kris.get("/api/v1/workouts/drafts/active")
        assert active.status_code == 200
        assert active.json()["version"] == 2
        assert active.json()["snapshot"]["phase"] == "ACTIVE_SET"
        assert kirsty.get("/api/v1/workouts/drafts/active").status_code == 404

        complete_payload = {
            "idempotency_key": "accept-complete-1",
            "completed_at": "2026-10-01T07:42:00Z",
            "event": _event_payload(),
        }
        completed = kris.post(
            f"/api/v1/workouts/drafts/{draft['draft_id']}/complete",
            json=complete_payload,
        )
        assert completed.status_code == 201
        assert completed.json()["revision_number"] == 1
        revision_one_id = completed.json()["revision_id"]

        replay = kris.post(
            f"/api/v1/workouts/drafts/{draft['draft_id']}/complete",
            json=complete_payload,
        )
        assert replay.status_code == 200
        assert replay.json()["revision_id"] == revision_one_id

        assert kirsty.get("/api/v1/workouts/foundation-acceptance-event").status_code == 404

        corrected = kris.post(
            "/api/v1/workouts/foundation-acceptance-event/corrections",
            json={
                "idempotency_key": "accept-correct-1",
                "reason": "Correct recorded session RPE",
                "corrected_at": "2026-10-01T08:00:00Z",
                "event": _event_payload(session_rpe=7),
            },
        )
        assert corrected.status_code == 201
        assert corrected.json()["revision_number"] == 2
        assert corrected.json()["supersedes_revision_number"] == 1

        effective_api = kris.get("/api/v1/workouts/foundation-acceptance-event")
        assert effective_api.status_code == 200
        assert effective_api.json()["revision_number"] == 2
        assert effective_api.json()["event"]["effort"]["session_rpe"] == "7"

        with Session(restarted_engine) as session:
            revisions = tuple(
                session.scalars(
                    select(WorkoutRevision)
                    .where(WorkoutRevision.event_id == "foundation-acceptance-event")
                    .order_by(WorkoutRevision.revision_number)
                ).all()
            )
            assert len(revisions) == 2
            effective = get_effective_workout(
                session,
                "hwa-kris",
                "foundation-acceptance-event",
            )
            assert effective is not None
            assert effective.revision_number == 2
            projection = project_workout_for_pep(_context(), effective).model_dump(
                mode="json", by_alias=True
            )

        assert projection["person_id"] == "person_a"
        assert projection["event_id"] == "foundation-acceptance-event"
        assert projection["revision_number"] == 2
        assert projection["supersedes_revision_number"] == 1
        assert projection["provenance"]["atomic_evidence_id"] == corrected.json()[
            "revision_id"
        ]
        assert "duration" not in projection
        assert "effort" not in projection
        assert projection["duration_seconds"] == 2520
        assert projection["session_rpe"] == "7"
    finally:
        kris.close()
        kirsty.close()
        restarted_engine.dispose()


@pytest.mark.asyncio
async def test_external_context_outage_never_blocks_durable_workout_authority() -> None:
    def offline(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    transport = httpx.MockTransport(offline)
    async with httpx.AsyncClient(transport=transport) as pep_client:
        pep = await PepHealthReader(pep_client).read(_context())
    async with httpx.AsyncClient(transport=transport) as menu_client:
        menu = await MenuNutritionReader(menu_client).read(_context())

    assert pep.status == "UNAVAILABLE"
    assert pep.reason == "PEP_HEALTH_UNAVAILABLE"
    assert menu.status == "UNAVAILABLE"
    assert menu.reason == "MENU_NUTRITION_UNAVAILABLE"
