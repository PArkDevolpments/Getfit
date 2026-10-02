"""Approved local technique-media metadata for canonical programme exercises.

Media is presentation support only. Programme authority, targets and workout evidence
remain valid even if an asset cannot be rendered.
"""

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class ExerciseMedia:
    exercise_id: str
    local_demo_path: str | None = None
    phase_demo_paths: tuple[str, ...] = ()
    phase_labels: tuple[str, ...] = ()
    external_video_url: str | None = None
    external_video_approved: bool = False

    @property
    def approved_external_video_url(self) -> str | None:
        if not self.external_video_approved or not self.external_video_url:
            return None
        parsed = urlparse(self.external_video_url)
        if parsed.scheme != "https" or not parsed.netloc:
            return None
        return self.external_video_url

    @property
    def available(self) -> bool:
        return bool(
            self.local_demo_path
            or self.phase_demo_paths
            or self.approved_external_video_url
        )


def _local(exercise_id: str, *, phases: tuple[str, ...] = ()) -> ExerciseMedia:
    root = "/static/media/exercises"
    phase_paths = tuple(f"{root}/{exercise_id}-{phase}.svg" for phase in phases)
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
    """Return approved local/linked media without making it programme authority."""

    key = exercise_id.strip()
    return _APPROVED_MEDIA.get(key, ExerciseMedia(exercise_id=key))
