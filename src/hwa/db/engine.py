"""SQLite engine configuration for Home Workout Assistant."""

from dataclasses import dataclass
from sqlite3 import Connection as SQLiteConnection
from typing import Any

from sqlalchemy import Engine, event
from sqlalchemy import create_engine as sqlalchemy_create_engine
from sqlalchemy.orm import Session, sessionmaker


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    """Database runtime settings."""

    database_url: str = "sqlite:///./hwa.db"
    busy_timeout_ms: int = 5000

    def __post_init__(self) -> None:
        if self.busy_timeout_ms <= 0:
            raise ValueError("busy_timeout_ms must be positive")


def create_engine(settings: DatabaseSettings | None = None) -> Engine:
    """Create an HWA engine with SQLite safety pragmas."""

    settings = settings or DatabaseSettings()
    engine = sqlalchemy_create_engine(settings.database_url)

    if settings.database_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _configure_sqlite(dbapi_connection: Any, connection_record: Any) -> None:
            del connection_record
            if not isinstance(dbapi_connection, SQLiteConnection):
                return
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute(f"PRAGMA busy_timeout={settings.busy_timeout_ms}")
                cursor.execute("PRAGMA journal_mode=WAL")
            finally:
                cursor.close()

    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create the synchronous Foundation session factory."""

    return sessionmaker(bind=engine, expire_on_commit=False)
