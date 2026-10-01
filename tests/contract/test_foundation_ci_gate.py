from pathlib import Path


def test_ci_runs_the_approved_foundation_quality_gate() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    required_commands = (
        "uv run ruff check .",
        "uv run mypy src",
        "uv run pytest tests/unit -q",
        "uv run pytest tests/integration -q",
        "uv run pytest tests/contract -q",
        "uv run pytest tests/e2e -q",
        "uv run alembic upgrade head",
    )
    for command in required_commands:
        assert command in workflow, f"Foundation CI gate missing: {command}"
