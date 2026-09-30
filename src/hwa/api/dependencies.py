"""Request-scoped API dependencies."""

from typing import cast

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session, sessionmaker

from hwa.auth.principal import AuthenticationError, PrincipalProvider
from hwa.domain.identity import IdentityNotMappedError, IdentityService, PersonContext
from hwa.repositories.identity import IdentityRepository


def resolve_person_context(request: Request) -> PersonContext:
    """Resolve the request's authenticated person without trusting client IDs."""

    provider = cast(PrincipalProvider, request.app.state.principal_provider)
    session_factory = cast(
        sessionmaker[Session], request.app.state.session_factory
    )

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
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": exc.code},
            ) from exc
