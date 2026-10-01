"""In-process Pep WORKOUT_EVENT_SOURCE provider boundary.

Transport/authentication is intentionally not exposed here. A later trusted integration
may transport this provider, but Task 8 does not add an unauthenticated HTTP endpoint.
"""

from sqlalchemy.orm import Session

from hwa.integrations.pep.schemas import (
    PepWorkoutSourceReadiness,
    PepWorkoutSourceRecordV1,
)
from hwa.integrations.pep.workout_export import export_workouts_for_pep
from hwa.repositories.identity import IdentityRepository


class PepWorkoutSourceProvider:
    """Match Pep's records(personId) + optional readiness(personId) provider interface."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def readiness(self, person_id: str) -> PepWorkoutSourceReadiness:
        pep_person_id = person_id.strip()
        if not pep_person_id:
            return PepWorkoutSourceReadiness(
                ready=False,
                state="UNAVAILABLE",
                reason="PERSON_ID_REQUIRED",
            )
        person = IdentityRepository(self._session).person_for_external_subject(
            "PEP_SITE", pep_person_id
        )
        if person is None or not person.active:
            return PepWorkoutSourceReadiness(
                ready=False,
                state="UNAVAILABLE",
                reason="PERSON_NOT_MAPPED",
            )
        return PepWorkoutSourceReadiness(ready=True, state="READY", reason="OK")

    def records(self, person_id: str) -> tuple[PepWorkoutSourceRecordV1, ...]:
        readiness = self.readiness(person_id)
        if not readiness.ready:
            return ()
        return export_workouts_for_pep(self._session, person_id)
