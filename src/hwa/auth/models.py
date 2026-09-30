"""Authentication value objects."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AuthenticatedPrincipal:
    """Stable subject established by an authentication provider."""

    subject_id: str
    display_name: str | None = None
