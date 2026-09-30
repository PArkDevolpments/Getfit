from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def _config(database_url: str) -> Config:
    config = Config(str(Path("alembic.ini")))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_workout_evidence_tables_are_created_by_migrations(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'evidence.db'}"
    command.upgrade(_config(database_url), "head")

    engine = create_engine(database_url)
    try:
        tables = set(inspect(engine).get_table_names())
        assert {"workout_events", "workout_revisions", "workout_idempotency_keys"} <= tables
    finally:
        engine.dispose()
