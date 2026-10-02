"""Exercise Library read model derived only from canonical programme exercise IDs."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from hwa.db.models.programme import ProgrammeStrengthItem
from hwa.domain.exercise_media import ExerciseMedia, resolve_exercise_media


@dataclass(frozen=True, slots=True)
class ExerciseLibraryItem:
    exercise_id: str
    display_name: str
    body_area: str
    movement_family: str
    technique_cues: tuple[str, ...]
    media: ExerciseMedia


_EXERCISE_GUIDANCE: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "dumbbell_floor_press": (
        "Chest · triceps",
        "Horizontal press",
        ("Set the shoulders", "Keep wrists stacked", "Lower the dumbbells under control"),
    ),
    "one_arm_dumbbell_row": (
        "Back · biceps",
        "Horizontal pull",
        ("Brace the support arm", "Pull the elbow towards the hip", "Lower under control"),
    ),
    "seated_dumbbell_shoulder_press": (
        "Shoulders · triceps",
        "Vertical press",
        ("Sit tall and brace", "Press without leaning back", "Lower under control"),
    ),
    "dumbbell_biceps_curl": (
        "Biceps",
        "Arm flexion",
        ("Keep elbows close", "Avoid swinging", "Control the lowering phase"),
    ),
    "overhead_triceps_extension": (
        "Triceps",
        "Arm extension",
        ("Keep ribs stacked", "Keep upper arms steady", "Move smoothly through the elbows"),
    ),
    "goblet_squat": (
        "Quads · glutes · core",
        "Squat",
        (
            "Keep the chest up",
            "Let knees track naturally over feet",
            "Drive through the whole foot",
        ),
    ),
    "dumbbell_romanian_deadlift": (
        "Posterior chain",
        "Hip hinge",
        ("Push the hips backward", "Keep knees softly bent", "Stand by driving the hips forward"),
    ),
    "supported_reverse_lunge": (
        "Quads · glutes",
        "Single-leg squat",
        ("Use the support for balance", "Step back under control", "Drive through the front foot"),
    ),
    "standing_calf_raise": (
        "Calves",
        "Calf raise",
        ("Stand tall", "Rise under control", "Lower through a comfortable range"),
    ),
    "dead_bug": (
        "Core",
        "Trunk control",
        ("Brace gently", "Move slowly", "Keep the lower back controlled"),
    ),
    "forearm_plank": (
        "Core · trunk",
        "Isometric hold",
        ("Make a long line head to heel", "Brace the trunk", "Stop before position breaks down"),
    ),
    "dumbbell_lateral_raise": (
        "Shoulders",
        "Shoulder raise",
        ("Use a light controlled load", "Keep a soft elbow", "Avoid shrugging the shoulders"),
    ),
    "hammer_curl": (
        "Biceps · forearms",
        "Arm flexion",
        ("Keep a neutral grip", "Keep elbows close", "Avoid swinging"),
    ),
}


def display_name(exercise_id: str) -> str:
    return exercise_id.replace("-", " ").replace("_", " ").title()


def _presentation(exercise_id: str) -> tuple[str, str, tuple[str, ...]]:
    return _EXERCISE_GUIDANCE.get(
        exercise_id,
        ("Programme exercise", "Strength movement", ()),
    )


def _item(exercise_id: str) -> ExerciseLibraryItem:
    body_area, movement_family, technique_cues = _presentation(exercise_id)
    return ExerciseLibraryItem(
        exercise_id=exercise_id,
        display_name=display_name(exercise_id),
        body_area=body_area,
        movement_family=movement_family,
        technique_cues=technique_cues,
        media=resolve_exercise_media(exercise_id),
    )


def list_exercises(session: Session) -> tuple[ExerciseLibraryItem, ...]:
    exercise_ids = tuple(
        session.scalars(
            select(ProgrammeStrengthItem.exercise_id)
            .distinct()
            .order_by(ProgrammeStrengthItem.exercise_id)
        ).all()
    )
    return tuple(_item(exercise_id) for exercise_id in exercise_ids)


def get_exercise(session: Session, exercise_id: str) -> ExerciseLibraryItem | None:
    exists = session.scalar(
        select(ProgrammeStrengthItem.id)
        .where(ProgrammeStrengthItem.exercise_id == exercise_id)
        .limit(1)
    )
    if exists is None:
        return None
    return _item(exercise_id)
