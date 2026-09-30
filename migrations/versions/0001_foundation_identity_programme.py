"""Foundation identity and programme schema.

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "people",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("canonical_key", sa.String(64), nullable=False, unique=True),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("presentation_profile", sa.String(32), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at_utc", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "external_identity_mappings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("person_id", sa.String(36), sa.ForeignKey("people.id", ondelete="CASCADE"), nullable=False),
        sa.Column("authority", sa.String(64), nullable=False),
        sa.Column("external_subject_id", sa.String(255), nullable=False),
        sa.Column("created_at_utc", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("authority", "external_subject_id", name="uq_external_authority_subject"),
        sa.UniqueConstraint("person_id", "authority", name="uq_person_authority"),
    )
    op.create_table(
        "programme_definitions",
        sa.Column("programme_id", sa.String(128), primary_key=True),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("seed_checksum", sa.String(128), nullable=False),
        sa.Column("created_at_utc", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "programme_days",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("programme_id", sa.String(128), sa.ForeignKey("programme_definitions.programme_id", ondelete="CASCADE"), nullable=False),
        sa.Column("week_number", sa.Integer(), nullable=False),
        sa.Column("day_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("workout_type", sa.String(64), nullable=False),
        sa.Column("block", sa.String(64), nullable=False),
        sa.UniqueConstraint("programme_id", "week_number", "day_number", name="uq_programme_week_day"),
    )
    op.create_table(
        "programme_strength_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("programme_day_id", sa.String(36), sa.ForeignKey("programme_days.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("exercise_id", sa.String(128), nullable=False),
        sa.Column("target_type", sa.String(16), nullable=False),
        sa.Column("sets_target", sa.Integer(), nullable=False),
        sa.Column("reps_target", sa.Integer()),
        sa.Column("reps_min", sa.Integer()),
        sa.Column("reps_max", sa.Integer()),
        sa.Column("duration_seconds_target", sa.Integer()),
        sa.Column("duration_seconds_min", sa.Integer()),
        sa.Column("duration_seconds_max", sa.Integer()),
        sa.Column("laterality", sa.String(16), nullable=False),
        sa.Column("load_value", sa.Numeric(8, 2)),
        sa.Column("load_unit", sa.String(16)),
        sa.Column("load_mode", sa.String(32), nullable=False),
        sa.Column("load_basis", sa.String(64)),
        sa.Column("rest_seconds_min", sa.Integer()),
        sa.Column("rest_seconds_max", sa.Integer()),
        sa.Column("tempo_eccentric_seconds", sa.Integer()),
        sa.Column("tempo_concentric_seconds", sa.Integer()),
        sa.Column("notes", sa.Text()),
        sa.UniqueConstraint("programme_day_id", "sequence", name="uq_strength_day_sequence"),
        sa.CheckConstraint("sets_target > 0", name="ck_strength_sets_positive"),
    )
    op.create_table(
        "programme_cardio_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("programme_day_id", sa.String(36), sa.ForeignKey("programme_days.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("equipment", sa.String(32), nullable=False),
        sa.Column("segment_type", sa.String(32), nullable=False),
        sa.Column("target_mode", sa.String(16), nullable=False),
        sa.Column("rounds", sa.Integer()),
        sa.Column("duration_seconds", sa.Integer()),
        sa.Column("speed_kmh", sa.Numeric(6, 2)),
        sa.Column("incline_percent", sa.Numeric(5, 2)),
        sa.Column("cadence_rpm_min", sa.Integer()),
        sa.Column("cadence_rpm_max", sa.Integer()),
        sa.Column("resistance", sa.String(32)),
        sa.Column("rpe_min", sa.Numeric(3, 1)),
        sa.Column("rpe_max", sa.Numeric(3, 1)),
        sa.UniqueConstraint("programme_day_id", "sequence", name="uq_cardio_day_sequence"),
        sa.CheckConstraint("equipment != 'spin_bike' OR incline_percent IS NULL", name="ck_spin_bike_no_incline"),
    )
    op.create_table(
        "person_programme_assignments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("person_id", sa.String(36), sa.ForeignKey("people.id"), nullable=False),
        sa.Column("programme_id", sa.String(128), sa.ForeignKey("programme_definitions.programme_id"), nullable=False),
        sa.Column("effective_from_utc", sa.DateTime(), nullable=False),
        sa.Column("effective_to_utc", sa.DateTime()),
        sa.Column("status", sa.String(32), nullable=False),
    )
    op.create_table(
        "person_prescription_overrides",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("person_id", sa.String(36), sa.ForeignKey("people.id"), nullable=False),
        sa.Column("programme_strength_item_id", sa.String(36), sa.ForeignKey("programme_strength_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("load_value", sa.Numeric(8, 2)),
        sa.Column("load_unit", sa.String(16)),
        sa.Column("load_mode", sa.String(32)),
        sa.Column("created_at_utc", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("person_id", "programme_strength_item_id", name="uq_person_strength_override"),
    )


def downgrade() -> None:
    op.drop_table("person_prescription_overrides")
    op.drop_table("person_programme_assignments")
    op.drop_table("programme_cardio_items")
    op.drop_table("programme_strength_items")
    op.drop_table("programme_days")
    op.drop_table("programme_definitions")
    op.drop_table("external_identity_mappings")
    op.drop_table("people")
