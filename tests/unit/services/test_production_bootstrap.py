from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from hwa.db.base import Base
from hwa.db.engine import DatabaseSettings, create_engine
from hwa.db.models.identity import ExternalIdentityMapping, Person
from hwa.services.production_bootstrap import (
    BootstrapConflictError,
    ProductionBootstrapConfig,
    ensure_production_identities,
)


def _session() -> tuple[Session, Engine]:
    engine = create_engine(DatabaseSettings(database_url="sqlite:///:memory:"))
    Base.metadata.create_all(engine)
    return Session(engine), engine


def _mapping_dict(session: Session, person_id: str) -> dict[str, str]:
    rows = session.scalars(
        select(ExternalIdentityMapping).where(ExternalIdentityMapping.person_id == person_id)
    ).all()
    return {row.authority: row.external_subject_id for row in rows}


def test_config_normalizes_missing_and_whitespace_home_assistant_ids() -> None:
    config = ProductionBootstrapConfig.from_raw("  ha-kris  ", "   ")

    assert config.kris_ha_user_id == "ha-kris"
    assert config.kirsty_ha_user_id is None
    assert ProductionBootstrapConfig.from_raw(None, "").kris_ha_user_id is None


def test_identity_bootstrap_creates_approved_people_and_fixed_authority_mappings() -> None:
    session, engine = _session()
    try:
        result = ensure_production_identities(
            session,
            ProductionBootstrapConfig.from_raw("ha-kris", None),
        )

        assert result.people_created == 2
        assert result.mappings_created == 7
        assert result.configured_person_ids == ("hwa-kris",)

        kris = session.get(Person, "hwa-kris")
        kirsty = session.get(Person, "hwa-kirsty")
        assert kris is not None
        assert (kris.canonical_key, kris.display_name, kris.presentation_profile, kris.active) == (
            "kris",
            "Kris",
            "male",
            True,
        )
        assert kirsty is not None
        assert (
            kirsty.canonical_key,
            kirsty.display_name,
            kirsty.presentation_profile,
            kirsty.active,
        ) == ("kirsty", "Kirsty", "female", True)

        assert _mapping_dict(session, "hwa-kris") == {
            "HOME_ASSISTANT": "ha-kris",
            "PEP_SITE": "person_a",
            "HEALTH_PROFILE": "kris",
            "MENU_NUTRITION": "person_1",
        }
        assert _mapping_dict(session, "hwa-kirsty") == {
            "PEP_SITE": "person_b",
            "HEALTH_PROFILE": "kirsty",
            "MENU_NUTRITION": "person_2",
        }
    finally:
        session.close()
        engine.dispose()


def test_same_home_assistant_subject_for_both_people_fails_before_writes() -> None:
    session, engine = _session()
    try:
        config = ProductionBootstrapConfig.from_raw("same-ha-id", "same-ha-id")

        try:
            ensure_production_identities(session, config)
        except BootstrapConflictError as exc:
            assert "HOME_ASSISTANT" in str(exc)
        else:
            raise AssertionError("duplicate configured HA subject must fail closed")

        assert session.scalar(select(Person).limit(1)) is None
        assert session.scalar(select(ExternalIdentityMapping).limit(1)) is None
    finally:
        session.close()
        engine.dispose()


def test_existing_person_metadata_conflict_fails_without_rewrite() -> None:
    session, engine = _session()
    try:
        session.add(
            Person(
                id="hwa-kris",
                canonical_key="kris",
                display_name="Not Kris",
                presentation_profile="male",
                active=True,
            )
        )
        session.commit()

        try:
            ensure_production_identities(
                session,
                ProductionBootstrapConfig.from_raw("ha-kris", None),
            )
        except BootstrapConflictError as exc:
            assert "hwa-kris" in str(exc)
        else:
            raise AssertionError("conflicting stable person metadata must fail closed")

        assert session.get(Person, "hwa-kris").display_name == "Not Kris"
    finally:
        session.close()
        engine.dispose()


def test_existing_person_authority_mapping_conflict_fails_without_reassignment() -> None:
    session, engine = _session()
    try:
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
        session.add(
            ExternalIdentityMapping(
                id="hwa-kris-home-assistant",
                person_id="hwa-kris",
                authority="HOME_ASSISTANT",
                external_subject_id="old-ha-id",
            )
        )
        session.commit()

        try:
            ensure_production_identities(
                session,
                ProductionBootstrapConfig.from_raw("new-ha-id", None),
            )
        except BootstrapConflictError as exc:
            assert "HOME_ASSISTANT" in str(exc)
        else:
            raise AssertionError("existing person/authority conflict must fail closed")

        mapping = session.scalar(
            select(ExternalIdentityMapping).where(
                ExternalIdentityMapping.person_id == "hwa-kris",
                ExternalIdentityMapping.authority == "HOME_ASSISTANT",
            )
        )
        assert mapping is not None
        assert mapping.external_subject_id == "old-ha-id"
    finally:
        session.close()
        engine.dispose()


def test_external_subject_owned_by_other_person_fails_without_reassignment() -> None:
    session, engine = _session()
    try:
        session.add(
            Person(
                id="someone-else",
                canonical_key="someone-else",
                display_name="Someone Else",
                presentation_profile="male",
                active=True,
            )
        )
        session.flush()
        session.add(
            ExternalIdentityMapping(
                id="someone-else-ha",
                person_id="someone-else",
                authority="HOME_ASSISTANT",
                external_subject_id="ha-kris",
            )
        )
        session.commit()

        try:
            ensure_production_identities(
                session,
                ProductionBootstrapConfig.from_raw("ha-kris", None),
            )
        except BootstrapConflictError as exc:
            assert "ha-kris" not in str(exc)
            assert "HOME_ASSISTANT" in str(exc)
        else:
            raise AssertionError("external subject ownership conflict must fail closed")

        mapping = session.scalar(
            select(ExternalIdentityMapping).where(
                ExternalIdentityMapping.authority == "HOME_ASSISTANT",
                ExternalIdentityMapping.external_subject_id == "ha-kris",
            )
        )
        assert mapping is not None
        assert mapping.person_id == "someone-else"
    finally:
        session.close()
        engine.dispose()
