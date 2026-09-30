"""Add immutable workout evidence and idempotency receipts.

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workout_events",
        sa.Column("event_id", sa.String(128), primary_key=True),
        sa.Column(
            "person_id",
            sa.String(36),
            sa.ForeignKey("people.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "programme_day_id",
            sa.String(36),
            sa.ForeignKey("programme_days.id"),
            nullable=False,
        ),
        sa.Column("effective_revision_number", sa.Integer(), nullable=False),
        sa.Column("created_at_utc", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "effective_revision_number > 0",
            name="ck_workout_event_effective_revision_positive",
        ),
    )
    op.create_index(
        "ix_workout_events_person_created",
        "workout_events",
        ["person_id", "created_at_utc"],
    )

    op.create_table(
        "workout_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "event_id",
            sa.String(128),
            sa.ForeignKey("workout_events.event_id"),
            nullable=False,
        ),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("supersedes_revision_number", sa.Integer()),
        sa.Column("canonical_json", sa.Text(), nullable=False),
        sa.Column("recorded_at_utc", sa.DateTime(), nullable=False),
        sa.Column("correction_reason", sa.Text()),
        sa.UniqueConstraint(
            "event_id", "revision_number", name="uq_workout_event_revision"
        ),
        sa.CheckConstraint("revision_number > 0", name="ck_workout_revision_positive"),
    )

    op.create_table(
        "workout_idempotency_keys",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "person_id",
            sa.String(36),
            sa.ForeignKey("people.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("command_type", sa.String(16), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column(
            "event_id",
            sa.String(128),
            sa.ForeignKey("workout_events.event_id"),
            nullable=False,
        ),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("created_at_utc", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "person_id", "idempotency_key", name="uq_workout_person_idempotency"
        ),
    )

    op.execute(
        """
        CREATE TRIGGER workout_revisions_no_update
        BEFORE UPDATE ON workout_revisions
        BEGIN
            SELECT RAISE(ABORT, 'workout revisions are immutable');
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER workout_revisions_no_delete
        BEFORE DELETE ON workout_revisions
        BEGIN
            SELECT RAISE(ABORT, 'workout revisions are immutable');
        END
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS workout_revisions_no_delete")
    op.execute("DROP TRIGGER IF EXISTS workout_revisions_no_update")
    op.drop_table("workout_idempotency_keys")
    op.drop_table("workout_revisions")
    op.drop_index("ix_workout_events_person_created", table_name="workout_events")
    op.drop_table("workout_events")
