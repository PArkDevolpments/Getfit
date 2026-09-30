"""Add mutable workout draft persistence.

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workout_drafts",
        sa.Column("id", sa.String(36), primary_key=True),
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
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot_json", sa.Text(), nullable=False),
        sa.Column("started_at_utc", sa.DateTime(), nullable=False),
        sa.Column("updated_at_utc", sa.DateTime(), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_workout_draft_version_positive"),
    )
    op.create_index(
        "ix_workout_drafts_person_status_updated",
        "workout_drafts",
        ["person_id", "status", "updated_at_utc"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workout_drafts_person_status_updated",
        table_name="workout_drafts",
    )
    op.drop_table("workout_drafts")
