from pathlib import Path

import pytest
from starlette.requests import Request


def _load_auth():
    assert Path("src/hwa/auth/ha_ingress.py").exists(), "HA ingress auth boundary must exist"
    from hwa.auth.ha_ingress import HomeAssistantIngressPrincipalProvider
    from hwa.auth.principal import AuthenticationError

    return HomeAssistantIngressPrincipalProvider, AuthenticationError


def _request(host: str, headers: dict[str, str] | None = None) -> Request:
    raw_headers = [
        (key.lower().encode("ascii"), value.encode("utf-8"))
        for key, value in (headers or {}).items()
    ]
    return Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "http",
            "path": "/api/v1/me",
            "headers": raw_headers,
            "client": (host, 12345),
            "server": ("hwa", 8099),
        }
    )


def test_trusted_ingress_resolves_stable_ha_user_id() -> None:
    provider_cls, _ = _load_auth()
    principal = provider_cls().resolve(
        _request(
            "172.30.32.2",
            {
                "X-Remote-User-Id": "ha-user-kris",
                "X-Remote-User-Display-Name": "Kris",
            },
        )
    )
    assert principal.subject_id == "ha-user-kris"
    assert principal.display_name == "Kris"


def test_direct_request_cannot_spoof_remote_user_header() -> None:
    provider_cls, error_cls = _load_auth()
    provider = provider_cls()
    with pytest.raises(error_cls) as exc:
        provider.resolve(_request("127.0.0.1", {"X-Remote-User-Id": "ha-user-kris"}))
    assert exc.value.code == "UNAUTHENTICATED_INGRESS"


def test_trusted_ingress_without_user_id_fails_closed() -> None:
    provider_cls, error_cls = _load_auth()
    with pytest.raises(error_cls) as exc:
        provider_cls().resolve(_request("172.30.32.2"))
    assert exc.value.code == "UNAUTHENTICATED_INGRESS"


def test_web_dependency_retains_only_provider_resolved_principal_in_request_state(tmp_path):
    from fastapi import FastAPI
    from sqlalchemy.orm import Session

    from hwa.auth.models import AuthenticatedPrincipal
    from hwa.db.base import Base
    from hwa.db.engine import DatabaseSettings, create_engine, create_session_factory
    from hwa.db.models.identity import ExternalIdentityMapping, Person
    from hwa.web.dependencies import resolve_web_person_context

    provider_cls, _ = _load_auth()
    engine = create_engine(DatabaseSettings(database_url=f"sqlite:///{tmp_path / 'identity.db'}"))
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            session.add(
                Person(
                    id="synthetic-local",
                    canonical_key="synthetic",
                    display_name="Synthetic",
                    presentation_profile="male",
                    active=True,
                )
            )
            session.flush()
            for authority, subject in {
                "HOME_ASSISTANT": "synthetic-ha",
                "PEP_SITE": "synthetic-pep",
                "HEALTH_PROFILE": "synthetic-profile",
                "MENU_NUTRITION": "synthetic-menu",
            }.items():
                session.add(
                    ExternalIdentityMapping(
                        id=authority,
                        person_id="synthetic-local",
                        authority=authority,
                        external_subject_id=subject,
                    )
                )
            session.commit()
        app = FastAPI()
        app.state.principal_provider = provider_cls()
        app.state.session_factory = create_session_factory(engine)
        request = _request("172.30.32.2", {"X-Remote-User-Id": "synthetic-ha"})
        request.scope["app"] = app
        person = resolve_web_person_context(request)
        assert person.hwa_person_id == "synthetic-local"
        assert isinstance(request.state.authenticated_principal, AuthenticatedPrincipal)
        assert request.state.authenticated_principal.subject_id == "synthetic-ha"
    finally:
        engine.dispose()
