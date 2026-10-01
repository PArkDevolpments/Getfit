"""Optional technique-media metadata for canonical programme exercises.

Media is presentation support only. An exercise remains valid and usable when no
media is registered, and external URLs are exposed only when explicitly approved.
"""

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class ExerciseMedia:
    exercise_id: str
    local_demo_path: str | None = None
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
        return bool(self.local_demo_path or self.approved_external_video_url)


# Technique media is intentionally empty until assets/links have been explicitly
# approved. Canonical exercise IDs still appear in the Library through programme data.
_APPROVED_MEDIA: dict[str, ExerciseMedia] = {}


def resolve_exercise_media(exercise_id: str) -> ExerciseMedia:
    """Return optional media without making media a programme dependency."""

    key = exercise_id.strip()
    return _APPROVED_MEDIA.get(key, ExerciseMedia(exercise_id=key))
