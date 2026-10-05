"""Exercise metadata used by Getfit UI and descriptive training analytics.

This catalogue is intentionally small and local. It only describes movements already used by
approved Getfit programme material; it does not import third-party exercise media or source code.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExerciseProfile:
    body_area: str
    movement_family: str
    technique_cues: tuple[str, ...]
    equipment: tuple[str, ...]
    primary_muscles: tuple[str, ...]
    secondary_muscles: tuple[str, ...] = ()


_PROFILES: dict[str, ExerciseProfile] = {
    "dumbbell_floor_press": ExerciseProfile(
        body_area="Chest · triceps",
        movement_family="Horizontal press",
        technique_cues=(
            "Set the shoulders",
            "Keep wrists stacked",
            "Lower the dumbbells under control",
        ),
        equipment=("Dumbbells",),
        primary_muscles=("chest",),
        secondary_muscles=("triceps", "shoulders"),
    ),
    "one_arm_dumbbell_row": ExerciseProfile(
        body_area="Back · biceps",
        movement_family="Horizontal pull",
        technique_cues=(
            "Brace the support arm",
            "Pull the elbow towards the hip",
            "Lower under control",
        ),
        equipment=("Dumbbells",),
        primary_muscles=("back",),
        secondary_muscles=("biceps", "shoulders"),
    ),
    "seated_dumbbell_shoulder_press": ExerciseProfile(
        body_area="Shoulders · triceps",
        movement_family="Vertical press",
        technique_cues=("Sit tall and brace", "Press without leaning back", "Lower under control"),
        equipment=("Dumbbells",),
        primary_muscles=("shoulders",),
        secondary_muscles=("triceps",),
    ),
    "dumbbell_biceps_curl": ExerciseProfile(
        body_area="Biceps",
        movement_family="Arm flexion",
        technique_cues=("Keep elbows close", "Avoid swinging", "Control the lowering phase"),
        equipment=("Dumbbells",),
        primary_muscles=("biceps",),
        secondary_muscles=("forearms",),
    ),
    "overhead_triceps_extension": ExerciseProfile(
        body_area="Triceps",
        movement_family="Arm extension",
        technique_cues=(\n            "Keep ribs stacked",\n            "Keep upper arms steady",\n            "Move smoothly through the elbows",\n        ),
        equipment=("Dumbbells",),
        primary_muscles=("triceps",),
    ),
    "goblet_squat": ExerciseProfile(
        body_area="Quads · glutes · core",
        movement_family="Squat",
        technique_cues=(
            "Keep the chest up",
            "Let knees track naturally over feet",
            "Drive through the whole foot",
        ),
        equipment=("Dumbbells",),
        primary_muscles=("quads", "glutes"),
        secondary_muscles=("core",),
    ),
    "dumbbell_romanian_deadlift": ExerciseProfile(
        body_area="Posterior chain",
        movement_family="Hip hinge",
        technique_cues=(\n            "Push the hips backward",\n            "Keep knees softly bent",\n            "Stand by driving the hips forward",\n        ),
        equipment=("Dumbbells",),
        primary_muscles=("hamstrings", "glutes"),
        secondary_muscles=("back",),
    ),
    "supported_reverse_lunge": ExerciseProfile(
        body_area="Quads · glutes",
        movement_family="Single-leg squat",
        technique_cues=(\n            "Use the support for balance",\n            "Step back under control",\n            "Drive through the front foot",\n        ),
        equipment=("Bodyweight",),
        primary_muscles=("quads", "glutes"),
        secondary_muscles=("hamstrings",),
    ),
    "standing_calf_raise": ExerciseProfile(
        body_area="Calves",
        movement_family="Calf raise",
        technique_cues=("Stand tall", "Rise under control", "Lower through a comfortable range"),
        equipment=("Bodyweight",),
        primary_muscles=("calves",),
    ),
    "dead_bug": ExerciseProfile(
        body_area="Core",
        movement_family="Trunk control",
        technique_cues=("Brace gently", "Move slowly", "Keep the lower back controlled"),
        equipment=("Bodyweight",),
        primary_muscles=("core",),
    ),
    "forearm_plank": ExerciseProfile(
        body_area="Core · trunk",
        movement_family="Isometric hold",
        technique_cues=(\n            "Make a long line head to heel",\n            "Brace the trunk",\n            "Stop before position breaks down",\n        ),
        equipment=("Bodyweight",),
        primary_muscles=("core",),
    ),
    "dumbbell_lateral_raise": ExerciseProfile(
        body_area="Shoulders",
        movement_family="Shoulder raise",
        technique_cues=(\n            "Use a light controlled load",\n            "Keep a soft elbow",\n            "Avoid shrugging the shoulders",\n        ),
        equipment=("Dumbbells",),
        primary_muscles=("shoulders",),
    ),
    "hammer_curl": ExerciseProfile(
        body_area="Biceps · forearms",
        movement_family="Arm flexion",
        technique_cues=("Keep a neutral grip", "Keep elbows close", "Avoid swinging"),
        equipment=("Dumbbells",),
        primary_muscles=("biceps",),
        secondary_muscles=("forearms",),
    ),
}

_ALIASES = {
    "floor_press": "dumbbell_floor_press",
}


def normalise_exercise_id(exercise_id: str) -> str:
    key = exercise_id.strip().lower().replace("-", "_")
    return _ALIASES.get(key, key)


def display_name(exercise_id: str) -> str:
    return exercise_id.replace("-", " ").replace("_", " ").title()


def exercise_profile(exercise_id: str) -> ExerciseProfile:
    key = normalise_exercise_id(exercise_id)
    return _PROFILES.get(
        key,
        ExerciseProfile(
            body_area="Programme exercise",
            movement_family="Strength movement",
            technique_cues=(),
            equipment=(),
            primary_muscles=(),
        ),
    )


MUSCLE_LABELS: dict[str, str] = {
    "chest": "Chest",
    "back": "Back",
    "shoulders": "Shoulders",
    "biceps": "Biceps",
    "triceps": "Triceps",
    "quads": "Quads",
    "hamstrings": "Hamstrings",
    "glutes": "Glutes",
    "calves": "Calves",
    "core": "Core",
    "forearms": "Forearms",
}

MUSCLE_ORDER: tuple[str, ...] = tuple(MUSCLE_LABELS)
