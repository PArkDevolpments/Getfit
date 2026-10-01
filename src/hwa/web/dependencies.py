"""Web-only identity resolution that can present setup guidance safely."""

from typing import cast

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session, sessionmaker

from hwa.auth.principal import AuthenticationError, PrincipalProvider
from hwa.domain.identity import IdentityNotMappedError, IdentityService, PersonContext
from hwa.repositories.identity import IdentityRepository


class WebIdentitySetupRequired(RuntimeError):
    """Authenticated Home Assistant subject has no Getfit person mapping yet."""

    def __init__(self, subject_id: str) -> None:
        super().__init__("WEB_IDENTITY_SETUP_REQUIRED")
        self.subject_id = subject_id


def resolve_web_person_context(request: Request) -> PersonContext:
    """Resolve web identity, preserving auth failures and surfacing setup when unmapped."""

    provider = cast(PrincipalProvider, request.app.state.principal_provider)
    session_factory = cast(sessionmaker[Session], request.app.state.session_factory)

    try:
        principal = provider.resolve(request)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": exc.code},
        ) from exc

    with session_factory() as session:
        try:
            return IdentityService(IdentityRepository(session)).resolve(principal)
        except IdentityNotMappedError as exc:
            raise WebIdentitySetupRequired(principal.subject_id) from exc
