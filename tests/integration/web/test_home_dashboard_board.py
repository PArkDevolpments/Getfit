from pathlib import Path

from sqlalchemy.orm import Session

from hwa.db.base import Base
from hwa.db.engine import DatabaseSettings, create_engine
from hwa.db.models.identity import Person
from hwa.services.programmes import import_week_seed
from hwa.web.home import build_home_dashboard

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "programme_seed" / "home-workout-12m-v1" / "programme.json"
WEEK = ROOT / "programme_seed" / "home-workout-12m-v1" / "week-01.json"


def _session(tmp_path) -> tuple[Session, object]:
    engine = create_engine(
        DatabaseSettings(database_url=f"sqlite:///{tmp_path / 'home-dashboard.db'}")
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add_all(
        [
            Person(
                id="hwa-kris",
                canonical_key="kris",
                display_name="Kris",
                presentation_profile="male",
                active=True,
            ),
            Person(
                id="hwa-kirsty",
                canonical_key="kirsty",
                display_name="Kirsty",
                presentation_profile="female",
                active=True,
            ),
        ]
    )
    session.commit()
    import_week_seed(session, MANIFEST, WEEK)
    session.commit()
    return session, engine


def test_home_dashboard_projects_design_board_data_from_real_week1_authority(tmp_path) -> None:
    session, engine = _session(tmp_path)
    try:
        dashboard = build_home_dashboard(
            session,
            person_id="hwa-kris",
            programme_id="home-workout-12m-v1",
            week_number=1,
            current_day_number=1,
            current_programme_day_id="home-workout-12m-v1-week-01-day-01",
        )

        assert dashboard.duration_label == "~ 40–45 min"
        assert dashboard.weekly_cardio_goal_minutes == 150
        assert dashboard.weekly_cardio_minutes == 0
        assert dashboard.last_workout is None
        assert len(dashboard.sessions) == 4
        assert dashboard.sessions[0].title == "Upper Body + Bike"
        assert dashboard.sessions[0].current is True
        assert dashboard.sessions[0].completed is False

        snapshot = {item.exercise_id: item for item in dashboard.prescription_snapshot}
        assert str(snapshot["dumbbell_floor_press"].load_value) == "6.00"
        assert snapshot["dumbbell_floor_press"].load_mode == "EACH_HAND"
        assert str(snapshot["one_arm_dumbbell_row"].load_value) == "10.00"
        assert str(snapshot["seated_dumbbell_shoulder_press"].load_value) == "5.00"
    finally:
        session.close()
        engine.dispose()


def test_home_dashboard_never_fabricates_unapproved_person_loads(tmp_path) -> None:
    session, engine = _session(tmp_path)
    try:
        dashboard = build_home_dashboard(
            session,
            person_id="hwa-kirsty",
            programme_id="home-workout-12m-v1",
            week_number=1,
            current_day_number=1,
            current_programme_day_id="home-workout-12m-v1-week-01-day-01",
        )

        assert dashboard.prescription_snapshot
        assert all(item.load_value is None for item in dashboard.prescription_snapshot)
    finally:
        session.close()
        engine.dispose()


def test_today_template_contains_board_sections_not_generic_dashboard_copy() -> None:
    template = (
        ROOT / "src" / "hwa" / "web" / "templates" / "foundation.html"
    ).read_text(encoding="utf-8")

    for marker in (
        "home-dashboard",
        "next-workout-card",
        "This week",
        "Last workout",
        "Progress snapshot",
        "Weekly cardio",
        "workout-selection",
        "Weekly Goal",
        "150 minutes of moderate activity",
    ):
        assert marker in template

    assert "progress-orb" not in template
