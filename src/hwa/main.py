"""Application bootstrap for Home Workout Assistant."""

from fastapi import FastAPI

APP_VERSION = "0.1.0"

app = FastAPI(title="Home Workout Assistant", version=APP_VERSION)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Return a minimal process health response."""

    return {
        "status": "ok",
        "service": "home-workout-assistant",
        "version": APP_VERSION,
    }
