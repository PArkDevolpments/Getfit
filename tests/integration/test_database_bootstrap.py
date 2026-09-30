from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

EXPECTED_TABLES = {
    "alembic_version",
    "people",
    "external_identity_mappings",
    "programme_definitions",
    "programme_days",
    "programme_strength_items",
    "programme_cardio_items",
    "person_programme_assignments",
    "person_prescription_overrides",
}


def _alembic_config(database_url: str) -> Config:
    config_path = Path("alembic.ini")
    assert config_path.exists(), "alembic.ini must exist"
    config = Config(str(config_path))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_fresh_database_upgrades_to_foundation_schema(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'foundation.db'}"
    command.upgrade(_alembic_config(database_url), "head")

    engine = create_engine(database_url)
    try:
        assert EXPECTED_TABLES <= set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_upgrade_head_is_replay_safe(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'replay.db'}"
    config = _alembic_config(database_url)
    command.upgrade(config, "head")
    command.upgrade(config, "head")

    engine = create_engine(database_url)
    try:
        assert EXPECTED_TABLES <= set(inspect(engine).get_table_names())
    finally:
        engine.dispose()
