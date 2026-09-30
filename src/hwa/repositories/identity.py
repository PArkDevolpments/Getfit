"""Person identity persistence queries."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from hwa.db.models.identity import ExternalIdentityMapping, Person


class IdentityRepository:
    """Query stable people and their external authority mappings."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def person_for_external_subject(
        self, authority: str, external_subject_id: str
    ) -> Person | None:
        statement = (
            select(Person)
            .join(
                ExternalIdentityMapping,
                ExternalIdentityMapping.person_id == Person.id,
            )
            .where(
                ExternalIdentityMapping.authority == authority,
                ExternalIdentityMapping.external_subject_id == external_subject_id,
            )
        )
        return self._session.scalar(statement)

    def external_mappings(self, person_id: str) -> dict[str, str]:
        statement = select(ExternalIdentityMapping).where(
            ExternalIdentityMapping.person_id == person_id
        )
        rows = self._session.scalars(statement).all()
        return {row.authority: row.external_subject_id for row in rows}
