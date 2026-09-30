from importlib import import_module
from importlib.util import find_spec
from pathlib import Path


def _engine_module():
    spec = find_spec("hwa.db.engine")
    assert spec is not None, "hwa.db.engine must exist"
    return import_module("hwa.db.engine")


def _pragma(connection, name: str):
    return connection.exec_driver_sql(f"PRAGMA {name}").scalar_one()


def test_sqlite_runtime_pragmas_are_enforced(tmp_path: Path) -> None:
    module = _engine_module()
    settings = module.DatabaseSettings(
        database_url=f"sqlite:///{tmp_path / 'hwa.db'}",
        busy_timeout_ms=5000,
    )
    engine = module.create_engine(settings)
    try:
        with engine.connect() as connection:
            assert str(_pragma(connection, "journal_mode")).lower() == "wal"
            assert int(_pragma(connection, "foreign_keys")) == 1
            assert int(_pragma(connection, "busy_timeout")) == 5000
    finally:
        engine.dispose()


def test_sqlite_runtime_pragmas_survive_application_restart(tmp_path: Path) -> None:
    module = _engine_module()
    settings = module.DatabaseSettings(
        database_url=f"sqlite:///{tmp_path / 'hwa.db'}",
        busy_timeout_ms=7000,
    )
    first = module.create_engine(settings)
    with first.connect() as connection:
        assert str(_pragma(connection, "journal_mode")).lower() == "wal"
    first.dispose()

    second = module.create_engine(settings)
    try:
        with second.connect() as connection:
            assert str(_pragma(connection, "journal_mode")).lower() == "wal"
            assert int(_pragma(connection, "foreign_keys")) == 1
            assert int(_pragma(connection, "busy_timeout")) == 7000
    finally:
        second.dispose()
