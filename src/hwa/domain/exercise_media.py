"""Approved local technique-media metadata for canonical programme exercises.

Media is presentation support only. Programme authority, targets and workout evidence
remain valid even if an asset cannot be rendered.
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExerciseMedia:
    exercise_id: str
    local_demo_path: str | None = None
    local_video_filename: str | None = None
    phase_demo_paths: tuple[str, ...] = ()
    phase_labels: tuple[str, ...] = ()

    @property
    def local_video_path(self) -> str | None:
        """Return the fixed Getfit route for a safe local MP4 filename."""

        if self.local_video_filename is None:
            return None
        if re.fullmatch(r"[a-z0-9_]+\.mp4", self.local_video_filename) is None:
            return None
        return f"/exercise-videos/{self.local_video_filename}"

    @property
    def available(self) -> bool:
        return bool(self.local_demo_path or self.local_video_path or self.phase_demo_paths)


def _local(
    exercise_id: str,
    *,
    phases: tuple[str, ...] = (),
) -> ExerciseMedia:
    root = "/static/media/exercises"
    phase_paths = tuple(f"{root}/phases/{exercise_id}-{phase}.svg" for phase in phases)
    phase_labels = tuple(
        {
            "start": "Start",
            "lower": "Lower",
            "drive": "Drive Up",
        }.get(phase, phase.replace("-", " ").title())
        for phase in phases
    )
    return ExerciseMedia(
        exercise_id=exercise_id,
        local_demo_path=f"{root}/{exercise_id}.svg",
        local_video_filename=f"{exercise_id}.mp4",
        phase_demo_paths=phase_paths,
        phase_labels=phase_labels,
    )


_APPROVED_MEDIA: dict[str, ExerciseMedia] = {
    "dumbbell_floor_press": _local(
        "dumbbell_floor_press",
        phases=("start", "lower", "drive"),
    ),
    "one_arm_dumbbell_row": _local("one_arm_dumbbell_row"),
    "seated_dumbbell_shoulder_press": _local("seated_dumbbell_shoulder_press"),
    "dumbbell_biceps_curl": _local("dumbbell_biceps_curl"),
    "overhead_triceps_extension": _local("overhead_triceps_extension"),
    "goblet_squat": _local(
        "goblet_squat",
        phases=("start", "lower", "drive"),
    ),
    "dumbbell_romanian_deadlift": _local(
        "dumbbell_romanian_deadlift",
        phases=("start", "lower", "drive"),
    ),
    "supported_reverse_lunge": _local("supported_reverse_lunge"),
    "standing_calf_raise": _local("standing_calf_raise"),
    "dead_bug": _local("dead_bug"),
    "forearm_plank": _local("forearm_plank"),
    "dumbbell_lateral_raise": _local("dumbbell_lateral_raise"),
    "hammer_curl": _local("hammer_curl"),
}


def resolve_exercise_media(exercise_id: str) -> ExerciseMedia:
    """Return approved local media without making it programme authority."""

    key = exercise_id.strip()
    return _APPROVED_MEDIA.get(key, ExerciseMedia(exercise_id=key))
