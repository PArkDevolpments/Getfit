"""Approved local technique-media metadata for canonical programme exercises.

Media is presentation support only. Programme authority, targets and workout evidence
remain valid even if an asset cannot be rendered.
"""

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse


@dataclass(frozen=True, slots=True)
class ExerciseMedia:
    exercise_id: str
    local_demo_path: str | None = None
    local_video_filename: str | None = None
    phase_demo_paths: tuple[str, ...] = ()
    phase_labels: tuple[str, ...] = ()
    external_video_url: str | None = None
    external_video_source: str | None = None
    external_video_approved: bool = False

    @property
    def local_video_path(self) -> str | None:
        """Return the fixed Getfit route for a safe local MP4 filename."""

        if self.local_video_filename is None:
            return None
        if re.fullmatch(r"[a-z0-9_]+\.mp4", self.local_video_filename) is None:
            return None
        return f"/exercise-videos/{self.local_video_filename}"

    @property
    def approved_external_video_url(self) -> str | None:
        if not self.external_video_approved or not self.external_video_url:
            return None
        parsed = urlparse(self.external_video_url)
        if parsed.scheme != "https" or not parsed.netloc:
            return None
        return self.external_video_url

    @property
    def approved_external_video_embed_url(self) -> str | None:
        """Return a privacy-enhanced YouTube embed only for explicitly approved videos."""

        approved = self.approved_external_video_url
        if not approved:
            return None

        parsed = urlparse(approved)
        host = parsed.netloc.lower().split(":", 1)[0]
        video_id: str | None = None

        if host in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
            if parsed.path != "/watch":
                return None
            video_id = parse_qs(parsed.query).get("v", [None])[0]
        elif host == "youtu.be":
            video_id = parsed.path.strip("/").split("/", 1)[0] or None
        else:
            return None

        if video_id is None or re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id) is None:
            return None
        return f"https://www.youtube-nocookie.com/embed/{video_id}"

    @property
    def available(self) -> bool:
        return bool(
            self.local_demo_path
            or self.local_video_path
            or self.phase_demo_paths
            or self.approved_external_video_url
        )


def _local(
    exercise_id: str,
    *,
    phases: tuple[str, ...] = (),
    video_url: str | None = None,
    video_source: str | None = None,
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
        local_video_filename=f"{exercise_id}.mp4" if video_url is not None else None,
        phase_demo_paths=phase_paths,
        phase_labels=phase_labels,
        external_video_url=video_url,
        external_video_source=video_source,
        external_video_approved=video_url is not None,
    )


_APPROVED_MEDIA: dict[str, ExerciseMedia] = {
    "dumbbell_floor_press": _local(
        "dumbbell_floor_press",
        phases=("start", "lower", "drive"),
        video_url="https://www.youtube.com/watch?v=T0Y3OBF1bNI",
        video_source="PureGym",
    ),
    "one_arm_dumbbell_row": _local(
        "one_arm_dumbbell_row",
        video_url="https://www.youtube.com/watch?v=ZRSGpBUVcNw",
        video_source="PureGym",
    ),
    "seated_dumbbell_shoulder_press": _local(
        "seated_dumbbell_shoulder_press",
        video_url="https://www.youtube.com/watch?v=TsduLWuhlFM",
        video_source="PureGym",
    ),
    "dumbbell_biceps_curl": _local(
        "dumbbell_biceps_curl",
        video_url="https://www.youtube.com/watch?v=MtXdEcW3Eog",
        video_source="PureGym",
    ),
    "overhead_triceps_extension": _local(
        "overhead_triceps_extension",
        video_url="https://www.youtube.com/watch?v=9wxRhONFsRA",
        video_source="PureGym",
    ),
    "goblet_squat": _local(
        "goblet_squat",
        phases=("start", "lower", "drive"),
        video_url="https://www.youtube.com/watch?v=zBV3ceGyAxw",
        video_source="PureGym",
    ),
    "dumbbell_romanian_deadlift": _local(
        "dumbbell_romanian_deadlift",
        phases=("start", "lower", "drive"),
        video_url="https://www.youtube.com/watch?v=zU-f6DMCdAI",
        video_source="PureGym",
    ),
    "supported_reverse_lunge": _local(
        "supported_reverse_lunge",
        video_url="https://www.youtube.com/watch?v=NuSAOvrwHbE",
        video_source="Body By Finn Fitness",
    ),
    "standing_calf_raise": _local(
        "standing_calf_raise",
        video_url="https://www.youtube.com/watch?v=Zep-wKHWkNM",
        video_source="PureGym",
    ),
    "dead_bug": _local(
        "dead_bug",
        video_url="https://www.youtube.com/watch?v=9RK9UUgKIQE",
        video_source="PureGym",
    ),
    "forearm_plank": _local(
        "forearm_plank",
        video_url="https://www.youtube.com/watch?v=q4rDeHYMcIg",
        video_source="PureGym",
    ),
    "dumbbell_lateral_raise": _local(
        "dumbbell_lateral_raise",
        video_url="https://www.youtube.com/watch?v=PzsMitRdI_8",
        video_source="Max Euceda",
    ),
    "hammer_curl": _local(
        "hammer_curl",
        video_url="https://www.youtube.com/watch?v=B4RznoFvTl4",
        video_source="PureGym",
    ),
}


def resolve_exercise_media(exercise_id: str) -> ExerciseMedia:
    """Return approved local/linked media without making it programme authority."""

    key = exercise_id.strip()
    return _APPROVED_MEDIA.get(key, ExerciseMedia(exercise_id=key))
