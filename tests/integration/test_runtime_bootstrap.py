from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

import hwa.runtime as runtime
from hwa.db.base import Base
from hwa.db.engine import DatabaseSettings, create_engine
from hwa.db.models.identity import Person
from hwa.db.models.programme import ProgrammeDay
from hwa.db.models.workout import WorkoutDraft, WorkoutEvent, WorkoutRevision
from hwa.main import create_app
from hwa.services.production_bootstrap import ProductionBootstrapConfig, bootstrap_production

ROOT = Path(__file__).resolve().parents[2]
SEED_ROOT = ROOT / "programme_seed"
MANIFEST = SEED_ROOT / "home-workout-12m-v1" / "programme.json"
WEEK = SEED_ROOT / "home-workout-12m-v1" / "week-01.json"
NOW = datetime(2026, 10, 1, 18, 45, tzinfo=UTC)


def _engine(tmp_path, name: str) -> Engine:
    engine = create_engine(DatabaseSettings(database_url=f"sqlite:///{tmp_path / name}"))
    Base.metadata.create_all(engine)
    return engine


def test_generic_create_app_does_not_seed_identity_or_programme(tmp_path) -> None:
    engine = _engine(tmp_path, "generic.db")
    try:
        create_app(engine=engine)
        with Session(engine) as session:
            assert session.scalar(select(Person).limit(1)) is None
    finally:
        engine.dispose()


def test_build_production_app_bootstraps_the_same_engine_it_serves(monkeypatch, tmp_path) -> None:
    engine = _engine(tmp_path, "production.db")
    monkeypatch.setattr(runtime, "create_engine", lambda: engine)
    monkeypatch.setenv("HWA_PROGRAMME_SEED_ROOT", str(SEED_ROOT))
    monkeypatch.setenv("HWA_KRIS_HA_USER_ID", "ha-user-kris")
    monkeypatch.setenv("HWA_KIRSTY_HA_USER_ID", "")

    try:
        app = runtime.build_production_app()

        with app.state.session_factory() as session:
            kris = session.get(Person, "hwa-kris")
            assert kris is not None
            assert kris.display_name == "Kris"
            assert session.scalar(select(ProgrammeDay).limit(1)) is not None
    finally:
        engine.dispose()


def test_bootstrap_replay_preserves_existing_draft_and_completed_revision(tmp_path) -> None:
    engine = _engine(tmp_path, "preserve.db")
    session = Session(engine)
    try:
        config = ProductionBootstrapConfig.from_raw("ha-user-kris", None)
        bootstrap_production(session, config, MANIFEST, WEEK, now=NOW)
        day = session.scalar(select(ProgrammeDay).order_by(ProgrammeDay.week_number, ProgrammeDay.day_number))
        assert day is not None

        draft = WorkoutDraft(
            id="existing-draft",
            person_id="hwa-kris",
            programme_day_id=day.id,
            status="ACTIVE",
            version=3,
            snapshot_json='{"phase":"ACTIVE_SET","state_data":{"note":"keep-me"}}',
            started_at_utc=NOW,
            updated_at_utc=NOW,
        )
        event = WorkoutEvent(
            event_id="existing-event",
            person_id="hwa-kris",
            programme_day_id=day.id,
            effective_revision_number=1,
            created_at_utc=NOW,
        )
        revision = WorkoutRevision(
            id="existing-revision",
            event_id="existing-event",
            revision_number=1,
            supersedes_revision_number=None,
            canonical_json='{"performance":{"completed":true}}',
            recorded_at_utc=NOW,
            correction_reason=None,
        )
        session.add_all([draft, event, revision])
        session.commit()

        draft_before = (
            draft.id,
            draft.status,
            draft.version,
            draft.snapshot_json,
            draft.started_at_utc,
            draft.updated_at_utc,
        )
        event_before = (
            event.event_id,
            event.effective_revision_number,
            event.created_at_utc,
        )
        revision_before = (
            revision.id,
            revision.revision_number,
            revision.canonical_json,
            revision.recorded_at_utc,
        )

        bootstrap_production(
            session,
            config,
            MANIFEST,
            WEEK,
            now=datetime(2026, 10, 2, 8, 0, tzinfo=UTC),
        )
        session.expire_all()

        replayed_draft = session.get(WorkoutDraft, "existing-draft")
        replayed_event = session.get(WorkoutEvent, "existing-event")
        replayed_revision = session.get(WorkoutRevision, "existing-revision")
        assert replayed_draft is not None
        assert replayed_event is not None
        assert replayed_revision is not None
        assert (
            replayed_draft.id,
            replayed_draft.status,
            replayed_draft.version,
            replayed_draft.snapshot_json,
            replayed_draft.started_at_utc,
            replayed_draft.updated_at_utc,
        ) == draft_before
        assert (
            replayed_event.event_id,
            replayed_event.effective_revision_number,
            replayed_event.created_at_utc,
        ) == event_before
        assert (
            replayed_revision.id,
            replayed_revision.revision_number,
            replayed_revision.canonical_json,
            replayed_revision.recorded_at_utc,
        ) == revision_before
    finally:
        session.close()
        engine.dispose()
