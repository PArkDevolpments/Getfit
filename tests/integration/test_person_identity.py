from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from hwa.db.base import Base
from hwa.db.engine import DatabaseSettings, create_engine
from hwa.db.models.identity import ExternalIdentityMapping, Person


def _load_identity():
    assert Path("src/hwa/domain/identity.py").exists(), "identity domain must exist"
    assert Path("src/hwa/repositories/identity.py").exists(), (
        "identity repository must exist"
    )
    from hwa.auth.models import AuthenticatedPrincipal
    from hwa.domain.identity import IdentityNotMappedError, IdentityService
    from hwa.repositories.identity import IdentityRepository

    return (
        AuthenticatedPrincipal,
        IdentityNotMappedError,
        IdentityService,
        IdentityRepository,
    )


def _seed(session: Session) -> None:
    kris = Person(
        id="hwa-kris",
        canonical_key="kris",
        display_name="Kris",
        presentation_profile="male",
        active=True,
    )
    kirsty = Person(
        id="hwa-kirsty",
        canonical_key="kirsty",
        display_name="Kirsty",
        presentation_profile="female",
        active=True,
    )
    session.add_all([kris, kirsty])
    session.flush()
    mappings = {
        "hwa-kris": {
            "HOME_ASSISTANT": "ha-user-kris",
            "PEP_SITE": "person_a",
            "HEALTH_PROFILE": "kris",
            "MENU_NUTRITION": "person_1",
        },
        "hwa-kirsty": {
            "HOME_ASSISTANT": "ha-user-kirsty",
            "PEP_SITE": "person_b",
            "HEALTH_PROFILE": "kirsty",
            "MENU_NUTRITION": "person_2",
        },
    }
    for person_id, authorities in mappings.items():
        for authority, subject in authorities.items():
            session.add(
                ExternalIdentityMapping(
                    id=f"{person_id}-{authority}",
                    person_id=person_id,
                    authority=authority,
                    external_subject_id=subject,
                )
            )
    session.commit()


def _service(tmp_path):
    principal_cls, error_cls, service_cls, repository_cls = _load_identity()
    engine = create_engine(
        DatabaseSettings(database_url=f"sqlite:///{tmp_path / 'identity.db'}")
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    _seed(session)
    service = service_cls(repository_cls(session))
    return principal_cls, error_cls, service, session, engine


def test_kris_resolves_to_correct_cross_system_identity(tmp_path) -> None:
    principal_cls, _, service, session, engine = _service(tmp_path)
    try:
        result = service.resolve(principal_cls("ha-user-kris", "Renamed Kris"))
        assert result.hwa_person_id == "hwa-kris"
        assert result.pep_person_id == "person_a"
        assert result.health_profile_id == "kris"
        assert result.menu_person_id == "person_1"
        assert result.presentation_profile == "male"
        assert result.display_name == "Kris"
    finally:
        session.close()
        engine.dispose()


def test_kirsty_resolves_independently(tmp_path) -> None:
    principal_cls, _, service, session, engine = _service(tmp_path)
    try:
        result = service.resolve(
            principal_cls("ha-user-kirsty", "Kirsty Display Changed")
        )
        assert (
            result.pep_person_id,
            result.health_profile_id,
            result.menu_person_id,
        ) == ("person_b", "kirsty", "person_2")
        assert result.hwa_person_id == "hwa-kirsty"
        assert result.presentation_profile == "female"
    finally:
        session.close()
        engine.dispose()


def test_unknown_ha_user_fails_closed(tmp_path) -> None:
    principal_cls, error_cls, service, session, engine = _service(tmp_path)
    try:
        with pytest.raises(error_cls) as exc:
            service.resolve(principal_cls("ha-user-unknown", None))
        assert exc.value.code == "IDENTITY_NOT_MAPPED"
    finally:
        session.close()
        engine.dispose()
