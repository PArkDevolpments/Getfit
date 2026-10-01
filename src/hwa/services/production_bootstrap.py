"""Fail-closed production bootstrap for stable Getfit identities."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from hwa.db.models.identity import ExternalIdentityMapping, Person


class BootstrapConflictError(RuntimeError):
    """Raised when production bootstrap would make identity authority ambiguous."""


@dataclass(frozen=True, slots=True)
class ProductionBootstrapConfig:
    kris_ha_user_id: str | None
    kirsty_ha_user_id: str | None

    @classmethod
    def from_raw(
        cls,
        kris_ha_user_id: str | None,
        kirsty_ha_user_id: str | None,
    ) -> "ProductionBootstrapConfig":
        return cls(
            kris_ha_user_id=_normalize_optional_id(kris_ha_user_id),
            kirsty_ha_user_id=_normalize_optional_id(kirsty_ha_user_id),
        )


@dataclass(frozen=True, slots=True)
class IdentityBootstrapResult:
    people_created: int
    mappings_created: int
    configured_person_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _ApprovedPerson:
    person_id: str
    canonical_key: str
    display_name: str
    presentation_profile: str
    fixed_mappings: tuple[tuple[str, str], ...]


_APPROVED_PEOPLE = (
    _ApprovedPerson(
        person_id="hwa-kris",
        canonical_key="kris",
        display_name="Kris",
        presentation_profile="male",
        fixed_mappings=(
            ("PEP_SITE", "person_a"),
            ("HEALTH_PROFILE", "kris"),
            ("MENU_NUTRITION", "person_1"),
        ),
    ),
    _ApprovedPerson(
        person_id="hwa-kirsty",
        canonical_key="kirsty",
        display_name="Kirsty",
        presentation_profile="female",
        fixed_mappings=(
            ("PEP_SITE", "person_b"),
            ("HEALTH_PROFILE", "kirsty"),
            ("MENU_NUTRITION", "person_2"),
        ),
    ),
)


def _normalize_optional_id(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _configured_ha_subjects(config: ProductionBootstrapConfig) -> dict[str, str]:
    configured: dict[str, str] = {}
    if config.kris_ha_user_id is not None:
        configured["hwa-kris"] = config.kris_ha_user_id
    if config.kirsty_ha_user_id is not None:
        configured["hwa-kirsty"] = config.kirsty_ha_user_id
    if len(set(configured.values())) != len(configured):
        raise BootstrapConflictError("HOME_ASSISTANT mapping conflict")
    return configured


def _mapping_id(person_id: str, authority: str) -> str:
    return f"{person_id}-{authority.lower().replace('_', '-')}"


def _desired_mappings(
    spec: _ApprovedPerson,
    configured_ha: dict[str, str],
) -> tuple[tuple[str, str], ...]:
    mappings = list(spec.fixed_mappings)
    subject = configured_ha.get(spec.person_id)
    if subject is not None:
        mappings.insert(0, ("HOME_ASSISTANT", subject))
    return tuple(mappings)


def _validate_person_preflight(session: Session, spec: _ApprovedPerson) -> Person | None:
    by_id = session.get(Person, spec.person_id)
    by_key = session.scalar(select(Person).where(Person.canonical_key == spec.canonical_key))

    if by_key is not None and by_key.id != spec.person_id:
        raise BootstrapConflictError(f"person {spec.person_id} metadata conflict")
    if by_id is None:
        return None
    if (
        by_id.canonical_key != spec.canonical_key
        or by_id.display_name != spec.display_name
        or by_id.presentation_profile != spec.presentation_profile
        or not by_id.active
    ):
        raise BootstrapConflictError(f"person {spec.person_id} metadata conflict")
    return by_id


def _validate_mapping_preflight(
    session: Session,
    person_id: str,
    authority: str,
    subject: str,
) -> ExternalIdentityMapping | None:
    by_person_authority = session.scalar(
        select(ExternalIdentityMapping).where(
            ExternalIdentityMapping.person_id == person_id,
            ExternalIdentityMapping.authority == authority,
        )
    )
    if by_person_authority is not None:
        if by_person_authority.external_subject_id != subject:
            raise BootstrapConflictError(f"{authority} mapping conflict")
        return by_person_authority

    by_subject = session.scalar(
        select(ExternalIdentityMapping).where(
            ExternalIdentityMapping.authority == authority,
            ExternalIdentityMapping.external_subject_id == subject,
        )
    )
    if by_subject is not None and by_subject.person_id != person_id:
        raise BootstrapConflictError(f"{authority} mapping conflict")

    deterministic_id = _mapping_id(person_id, authority)
    by_id = session.get(ExternalIdentityMapping, deterministic_id)
    if by_id is not None and (
        by_id.person_id != person_id
        or by_id.authority != authority
        or by_id.external_subject_id != subject
    ):
        raise BootstrapConflictError(f"{authority} mapping conflict")
    return by_id


def ensure_production_identities(
    session: Session,
    config: ProductionBootstrapConfig,
) -> IdentityBootstrapResult:
    """Ensure approved people/mappings exist without ever rewriting conflicts."""

    configured_ha = _configured_ha_subjects(config)
    existing_people: dict[str, Person | None] = {}
    existing_mappings: dict[tuple[str, str], ExternalIdentityMapping | None] = {}

    for spec in _APPROVED_PEOPLE:
        existing_people[spec.person_id] = _validate_person_preflight(session, spec)
        for authority, subject in _desired_mappings(spec, configured_ha):
            existing_mappings[(spec.person_id, authority)] = _validate_mapping_preflight(
                session,
                spec.person_id,
                authority,
                subject,
            )

    people_created = 0
    for spec in _APPROVED_PEOPLE:
        if existing_people[spec.person_id] is None:
            session.add(
                Person(
                    id=spec.person_id,
                    canonical_key=spec.canonical_key,
                    display_name=spec.display_name,
                    presentation_profile=spec.presentation_profile,
                    active=True,
                )
            )
            people_created += 1
    session.flush()

    mappings_created = 0
    for spec in _APPROVED_PEOPLE:
        for authority, subject in _desired_mappings(spec, configured_ha):
            if existing_mappings[(spec.person_id, authority)] is not None:
                continue
            session.add(
                ExternalIdentityMapping(
                    id=_mapping_id(spec.person_id, authority),
                    person_id=spec.person_id,
                    authority=authority,
                    external_subject_id=subject,
                )
            )
            mappings_created += 1
    session.flush()

    configured_person_ids = tuple(
        spec.person_id for spec in _APPROVED_PEOPLE if spec.person_id in configured_ha
    )
    return IdentityBootstrapResult(
        people_created=people_created,
        mappings_created=mappings_created,
        configured_person_ids=configured_person_ids,
    )
