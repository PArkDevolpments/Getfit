"""Fail-closed production bootstrap for stable Getfit identities and programme state."""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from hwa.db.models.identity import ExternalIdentityMapping, Person
from hwa.db.models.programme import PersonProgrammeAssignment
from hwa.services.programmes import import_week_seed

PROGRAMME_ID = "home-workout-12m-v1"


class BootstrapConflictError(RuntimeError):
    """Raised when production bootstrap would make authority ambiguous."""


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
class BootstrapResult:
    people_created: int
    mappings_created: int
    assignments_created: int
    programme_changed: bool


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


def _assignment_id(person_id: str, programme_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"{person_id}:{programme_id}:active-assignment"))


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


def _validate_assignment_preflight(
    session: Session,
    configured_person_ids: tuple[str, ...],
) -> dict[str, PersonProgrammeAssignment | None]:
    existing: dict[str, PersonProgrammeAssignment | None] = {}
    for person_id in configured_person_ids:
        active = session.scalars(
            select(PersonProgrammeAssignment).where(
                PersonProgrammeAssignment.person_id == person_id,
                PersonProgrammeAssignment.status == "ACTIVE",
            )
        ).all()
        if len(active) > 1:
            raise BootstrapConflictError(f"person {person_id} has multiple active programmes")
        if active and active[0].programme_id != PROGRAMME_ID:
            raise BootstrapConflictError(f"person {person_id} has conflicting active programme")
        if active:
            existing[person_id] = active[0]
            continue

        deterministic_id = _assignment_id(person_id, PROGRAMME_ID)
        by_id = session.get(PersonProgrammeAssignment, deterministic_id)
        if by_id is not None:
            raise BootstrapConflictError(f"person {person_id} assignment identity conflict")
        existing[person_id] = None
    return existing


def ensure_production_identities(
    session: Session,
    config: ProductionBootstrapConfig,
) -> IdentityBootstrapResult:
    """Ensure approved people/mappings exist without ever rewriting conflicts."""

    configured_ha = _configured_ha_subjects(config)
    existing_people: dict[str, Person | None] = {}
    existing_mappings: dict[tuple[str, str], ExternalIdentityMapping | None] = {}
    stale_home_assistant_mappings: list[ExternalIdentityMapping] = []

    for spec in _APPROVED_PEOPLE:
        existing_people[spec.person_id] = _validate_person_preflight(session, spec)
        for authority, subject in _desired_mappings(spec, configured_ha):
            existing_mappings[(spec.person_id, authority)] = _validate_mapping_preflight(
                session,
                spec.person_id,
                authority,
                subject,
            )
        if spec.person_id not in configured_ha:
            stale = session.scalar(
                select(ExternalIdentityMapping).where(
                    ExternalIdentityMapping.person_id == spec.person_id,
                    ExternalIdentityMapping.authority == "HOME_ASSISTANT",
                )
            )
            if stale is not None:
                stale_home_assistant_mappings.append(stale)

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

    for mapping in stale_home_assistant_mappings:
        session.delete(mapping)
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


def bootstrap_production(
    session: Session,
    config: ProductionBootstrapConfig,
    manifest_path: Path,
    week_path: Path,
    *,
    now: datetime | None = None,
) -> BootstrapResult:
    """Bootstrap approved identity, programme and assignments idempotently."""

    configured_person_ids = tuple(_configured_ha_subjects(config))
    existing_assignments = _validate_assignment_preflight(session, configured_person_ids)

    try:
        identity = ensure_production_identities(session, config)
        programme = import_week_seed(session, manifest_path, week_path)

        effective_from = now or datetime.now(UTC)
        assignments_created = 0
        for person_id in identity.configured_person_ids:
            if existing_assignments[person_id] is not None:
                continue
            session.add(
                PersonProgrammeAssignment(
                    id=_assignment_id(person_id, PROGRAMME_ID),
                    person_id=person_id,
                    programme_id=PROGRAMME_ID,
                    effective_from_utc=effective_from,
                    effective_to_utc=None,
                    status="ACTIVE",
                )
            )
            assignments_created += 1
        session.commit()
    except Exception:
        session.rollback()
        raise

    return BootstrapResult(
        people_created=identity.people_created,
        mappings_created=identity.mappings_created,
        assignments_created=assignments_created,
        programme_changed=programme.changed,
    )
