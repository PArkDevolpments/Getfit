"""Stable person identity resolution across HWA integrations."""

from dataclasses import dataclass

from hwa.auth.models import AuthenticatedPrincipal
from hwa.repositories.identity import IdentityRepository

_REQUIRED_AUTHORITIES = ("PEP_SITE", "HEALTH_PROFILE", "MENU_NUTRITION")


class IdentityNotMappedError(RuntimeError):
    """Raised when authenticated identity cannot be proven end-to-end."""

    def __init__(self, code: str = "IDENTITY_NOT_MAPPED") -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class PersonContext:
    """Resolved stable person context for one authenticated request."""

    hwa_person_id: str
    pep_person_id: str
    health_profile_id: str
    menu_person_id: str
    presentation_profile: str
    display_name: str


class IdentityService:
    """Resolve an authenticated Home Assistant subject to one HWA person."""

    def __init__(self, repository: IdentityRepository) -> None:
        self._repository = repository

    def resolve(self, principal: AuthenticatedPrincipal) -> PersonContext:
        person = self._repository.person_for_external_subject(
            "HOME_ASSISTANT", principal.subject_id
        )
        if person is None or not person.active:
            raise IdentityNotMappedError()

        mappings = self._repository.external_mappings(person.id)
        if any(authority not in mappings for authority in _REQUIRED_AUTHORITIES):
            raise IdentityNotMappedError("IDENTITY_MAPPING_INCOMPLETE")

        return PersonContext(
            hwa_person_id=person.id,
            pep_person_id=mappings["PEP_SITE"],
            health_profile_id=mappings["HEALTH_PROFILE"],
            menu_person_id=mappings["MENU_NUTRITION"],
            presentation_profile=person.presentation_profile,
            display_name=person.display_name,
        )
