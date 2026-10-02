"""Design-board Home dashboard projection over approved Getfit authority."""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from hwa.db.models.programme import ProgrammeDay
from hwa.read_models.history import get_weekly_cardio_minutes, get_workout_history
from hwa.web.workout import get_strength_targets


@dataclass(frozen=True, slots=True)
class HomeSessionCard:
    day_number: int
    title: str
    workout_type: str
    duration_label: str | None
    completed: bool
    current: bool


@dataclass(frozen=True, slots=True)
class PrescriptionSnapshotItem:
    exercise_id: str
    display_name: str
    load_value: Decimal | None
    load_unit: str | None
    load_mode: str
    load_label: str


@dataclass(frozen=True, slots=True)
class LastWorkoutSummary:
    programme_week: int | None
    programme_day: int | None
    day_label: str
    weekday_label: str


@dataclass(frozen=True, slots=True)
class HomeDashboard:
    sessions: tuple[HomeSessionCard, ...]
    duration_label: str | None
    prescription_snapshot: tuple[PrescriptionSnapshotItem, ...]
    last_workout: LastWorkoutSummary | None
    weekly_cardio_minutes: int
    weekly_cardio_percent: int
    weekly_cardio_goal_minutes: int = 150


_APPROVED_WEEK1_DURATION: dict[int, str] = {
    1: "~ 40–45 min",
    2: "~ 40–45 min",
    3: "~ 40–45 min",
    4: "~ 40–45 min",
}


def _duration_label(programme_id: str, week_number: int, day_number: int) -> str | None:
    if programme_id != "home-workout-12m-v1" or week_number != 1:
        return None
    return _APPROVED_WEEK1_DURATION.get(day_number)


_HOME_SNAPSHOT_LABELS = {
    "dumbbell_floor_press": "Floor press",
    "one_arm_dumbbell_row": "Row",
    "seated_dumbbell_shoulder_press": "Shoulder press",
}


def _exercise_display_name(exercise_id: str) -> str:
    return _HOME_SNAPSHOT_LABELS.get(
        exercise_id,
        exercise_id.replace("_", " ").replace("-", " ").title(),
    )


def _load_label(value: Decimal | None, unit: str | None, mode: str) -> str:
    if value is None:
        return "Calibration"
    amount = format(value.normalize(), "f")
    suffix = (unit or "KG").lower()
    if mode == "EACH_HAND":
        return f"{amount} {suffix} each"
    return f"{amount} {suffix}"


def build_home_dashboard(
    session: Session,
    *,
    person_id: str,
    programme_id: str,
    week_number: int,
    current_day_number: int | None,
    current_programme_day_id: str | None,
) -> HomeDashboard:
    """Build the live Home screen only from approved programme/person evidence."""

    history = get_workout_history(session, person_id)
    completed_days = {
        row.programme_day
        for row in history
        if row.programme_id == programme_id
        and row.programme_week == week_number
        and row.programme_day is not None
    }
    days = tuple(
        session.scalars(
            select(ProgrammeDay)
            .where(
                ProgrammeDay.programme_id == programme_id,
                ProgrammeDay.week_number == week_number,
            )
            .order_by(ProgrammeDay.day_number)
        ).all()
    )
    sessions = tuple(
        HomeSessionCard(
            day_number=day.day_number,
            title=day.title,
            workout_type=day.workout_type,
            duration_label=_duration_label(programme_id, week_number, day.day_number),
            completed=day.day_number in completed_days,
            current=day.day_number == current_day_number,
        )
        for day in days
    )

    targets = (
        get_strength_targets(session, person_id, current_programme_day_id)
        if current_programme_day_id is not None
        else ()
    )
    prescription_snapshot = tuple(
        PrescriptionSnapshotItem(
            exercise_id=target.exercise_id,
            display_name=_exercise_display_name(target.exercise_id),
            load_value=target.load_value,
            load_unit=target.load_unit,
            load_mode=target.load_mode,
            load_label=_load_label(target.load_value, target.load_unit, target.load_mode),
        )
        for target in targets[:3]
    )

    last = history[0] if history else None
    last_workout = (
        LastWorkoutSummary(
            programme_week=last.programme_week,
            programme_day=last.programme_day,
            day_label=(
                f"Day {last.programme_day}"
                if last.programme_day is not None
                else "Workout"
            ),
            weekday_label=last.start_at.strftime("%A"),
        )
        if last is not None
        else None
    )

    duration_label = (
        _duration_label(programme_id, week_number, current_day_number)
        if current_day_number is not None
        else None
    )
    weekly_cardio_minutes = get_weekly_cardio_minutes(
        session,
        person_id,
        programme_id,
        week_number,
    )
    return HomeDashboard(
        sessions=sessions,
        duration_label=duration_label,
        prescription_snapshot=prescription_snapshot,
        last_workout=last_workout,
        weekly_cardio_minutes=weekly_cardio_minutes,
        weekly_cardio_percent=min(100, round((weekly_cardio_minutes / 150) * 100)),
    )
