from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def _alembic_config(database_url: str) -> Config:
    config = Config(str(Path("alembic.ini")))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_workout_draft_table_is_created_by_migrations(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'draft-migration.db'}"
    command.upgrade(_alembic_config(database_url), "head")

    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        assert "workout_drafts" in inspector.get_table_names()
        columns = {column["name"] for column in inspector.get_columns("workout_drafts")}
        assert {
            "id",
            "person_id",
            "programme_day_id",
            "status",
            "version",
            "snapshot_json",
            "started_at_utc",
            "updated_at_utc",
        } <= columns
    finally:
        engine.dispose()
