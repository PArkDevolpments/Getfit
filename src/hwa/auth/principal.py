"""Principal provider interfaces and explicit test/development provider."""

from typing import Protocol

from starlette.requests import Request

from hwa.auth.models import AuthenticatedPrincipal


class AuthenticationError(RuntimeError):
    """Fail-closed authentication failure with a stable machine code."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class PrincipalProvider(Protocol):
    """Resolve an authenticated principal from an inbound request."""

    def resolve(self, request: Request) -> AuthenticatedPrincipal: ...


class StaticPrincipalProvider:
    """Explicit injected provider for tests/development only."""

    def __init__(self, subject_id: str, display_name: str | None = None) -> None:
        self._principal = AuthenticatedPrincipal(subject_id, display_name)

    def resolve(self, request: Request) -> AuthenticatedPrincipal:
        del request
        return self._principal
