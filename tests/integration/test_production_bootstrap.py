from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from hwa.db.base import Base
from hwa.db.engine import DatabaseSettings, create_engine
from hwa.db.models.identity import ExternalIdentityMapping, Person
from hwa.db.models.programme import (
    PersonPrescriptionOverride,
    PersonProgrammeAssignment,
    ProgrammeDay,
    ProgrammeDefinition,
)
from hwa.services.production_bootstrap import ProductionBootstrapConfig, bootstrap_production

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "programme_seed" / "home-workout-12m-v1" / "programme.json"
WEEK = ROOT / "programme_seed" / "home-workout-12m-v1" / "week-01.json"
PROGRAMME_ID = "home-workout-12m-v1"
NOW = datetime(2026, 10, 1, 18, 30, tzinfo=UTC)


def _session() -> tuple[Session, Engine]:
    engine = create_engine(DatabaseSettings(database_url="sqlite:///:memory:"))
    Base.metadata.create_all(engine)
    return Session(engine), engine


def _count(session: Session, model: type[object]) -> int:
    value = session.scalar(select(func.count()).select_from(model))
    assert value is not None
    return value


def test_cold_bootstrap_imports_week1_and_assigns_only_configured_kris() -> None:
    session, engine = _session()
    try:
        result = bootstrap_production(
            session,
            ProductionBootstrapConfig.from_raw("ha-kris", None),
            MANIFEST,
            WEEK,
            now=NOW,
        )

        assert result.people_created == 2
        assert result.mappings_created == 7
        assert result.assignments_created == 1
        assert result.programme_changed is True
        assert session.get(ProgrammeDefinition, PROGRAMME_ID) is not None
        assert _count(session, ProgrammeDay) == 4
        assert _count(session, PersonPrescriptionOverride) > 0

        assignments = session.scalars(select(PersonProgrammeAssignment)).all()
        assert len(assignments) == 1
        assignment = assignments[0]
        assert assignment.person_id == "hwa-kris"
        assert assignment.programme_id == PROGRAMME_ID
        assert assignment.status == "ACTIVE"
        assert assignment.effective_from_utc == NOW
        assert assignment.effective_to_utc is None

        kirsty_ha = session.scalar(
            select(ExternalIdentityMapping).where(
                ExternalIdentityMapping.person_id == "hwa-kirsty",
                ExternalIdentityMapping.authority == "HOME_ASSISTANT",
            )
        )
        assert kirsty_ha is None
        assert session.get(Person, "hwa-kirsty") is not None
    finally:
        session.close()
        engine.dispose()


def test_bootstrap_replay_is_idempotent_and_preserves_assignment_start() -> None:
    session, engine = _session()
    try:
        first = bootstrap_production(
            session,
            ProductionBootstrapConfig.from_raw("ha-kris", None),
            MANIFEST,
            WEEK,
            now=NOW,
        )
        assert first.assignments_created == 1
        assignment = session.scalar(
            select(PersonProgrammeAssignment).where(
                PersonProgrammeAssignment.person_id == "hwa-kris",
                PersonProgrammeAssignment.programme_id == PROGRAMME_ID,
                PersonProgrammeAssignment.status == "ACTIVE",
            )
        )
        assert assignment is not None
        original_effective_from = assignment.effective_from_utc

        counts_before = {
            "people": _count(session, Person),
            "mappings": _count(session, ExternalIdentityMapping),
            "programmes": _count(session, ProgrammeDefinition),
            "days": _count(session, ProgrammeDay),
            "overrides": _count(session, PersonPrescriptionOverride),
            "assignments": _count(session, PersonProgrammeAssignment),
        }

        second = bootstrap_production(
            session,
            ProductionBootstrapConfig.from_raw("ha-kris", None),
            MANIFEST,
            WEEK,
            now=datetime(2026, 10, 2, 9, 0, tzinfo=UTC),
        )

        assert second.people_created == 0
        assert second.mappings_created == 0
        assert second.assignments_created == 0
        assert second.programme_changed is False
        counts_after = {
            "people": _count(session, Person),
            "mappings": _count(session, ExternalIdentityMapping),
            "programmes": _count(session, ProgrammeDefinition),
            "days": _count(session, ProgrammeDay),
            "overrides": _count(session, PersonPrescriptionOverride),
            "assignments": _count(session, PersonProgrammeAssignment),
        }
        assert counts_after == counts_before

        replayed = session.get(PersonProgrammeAssignment, assignment.id)
        assert replayed is not None
        assert replayed.effective_from_utc == original_effective_from
    finally:
        session.close()
        engine.dispose()


def test_bootstrap_assigns_each_explicitly_configured_person_once() -> None:
    session, engine = _session()
    try:
        result = bootstrap_production(
            session,
            ProductionBootstrapConfig.from_raw("ha-kris", "ha-kirsty"),
            MANIFEST,
            WEEK,
            now=NOW,
        )

        assert result.assignments_created == 2
        assignments = session.scalars(
            select(PersonProgrammeAssignment)
            .where(
                PersonProgrammeAssignment.programme_id == PROGRAMME_ID,
                PersonProgrammeAssignment.status == "ACTIVE",
            )
            .order_by(PersonProgrammeAssignment.person_id)
        ).all()
        assert [row.person_id for row in assignments] == ["hwa-kirsty", "hwa-kris"]
        assert all(row.effective_from_utc == NOW for row in assignments)
    finally:
        session.close()
        engine.dispose()
