"""Persistent stable-person identity models."""

from datetime import UTC, datetime

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from hwa.db.base import Base
from hwa.db.timestamp import UTCDateTime


def utc_now() -> datetime:
    return datetime.now(UTC)


class Person(Base):
    """Stable HWA person identity."""

    __tablename__ = "people"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    canonical_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    presentation_profile: Mapped[str] = mapped_column(String(32), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at_utc: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)

    external_mappings: Mapped[list["ExternalIdentityMapping"]] = relationship(
        back_populates="person", cascade="all, delete-orphan"
    )


class ExternalIdentityMapping(Base):
    """Stable mapping to another authority's subject identifier."""

    __tablename__ = "external_identity_mappings"
    __table_args__ = (
        UniqueConstraint("authority", "external_subject_id", name="uq_external_authority_subject"),
        UniqueConstraint("person_id", "authority", name="uq_person_authority"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    person_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("people.id", ondelete="CASCADE"), nullable=False
    )
    authority: Mapped[str] = mapped_column(String(64), nullable=False)
    external_subject_id: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at_utc: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)

    person: Mapped[Person] = relationship(back_populates="external_mappings")
