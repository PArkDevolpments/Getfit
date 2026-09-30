"""Runtime configuration defaults for Home Workout Assistant."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    """Minimal Foundation settings."""

    household_timezone: str = "Europe/London"


settings = Settings()
