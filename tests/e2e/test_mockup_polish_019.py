from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "src" / "hwa" / "web" / "static"
TEMPLATES = ROOT / "src" / "hwa" / "web" / "templates"


def test_019_active_strength_does_not_render_rest_panel_before_rest_state() -> None:
    workout = (TEMPLATES / "workout.html").read_text(encoding="utf-8")
    css = (STATIC / "visual-refresh.css").read_text(encoding="utf-8")

    assert 'data-main-rest-panel {% if review_state|default(\'\') != \'strength-rest\' %}hidden{% endif %}' in workout
    assert ".main-rest-panel[hidden]" in css
    hidden_block = css.split(".main-rest-panel[hidden]", 1)[1].split("}", 1)[0]
    assert "display: none !important;" in hidden_block


def test_019_rest_state_uses_photographic_recovery_media() -> None:
    workout = (TEMPLATES / "workout.html").read_text(encoding="utf-8")
    rest_media = (STATIC / "media" / "cardio" / "rest-recovery.svg").read_text(
        encoding="utf-8"
    )

    assert 'class="rest-state-photo"' in workout
    assert "/static/media/cardio/rest-recovery.svg" in workout
    assert "data:image/webp;base64," in rest_media
    assert "<path" not in rest_media
    assert "<circle" not in rest_media


def test_019_treadmill_media_is_a_real_local_photo_not_the_blurred_placeholder() -> None:
    treadmill = (STATIC / "media" / "cardio" / "treadmill.svg").read_text(
        encoding="utf-8"
    )

    assert 'viewBox="0 0 480 360"' in treadmill
    assert "data:image/webp;base64," in treadmill
    assert len(treadmill) > 12000


def test_019_phone_rest_photo_stays_compact_and_viewport_safe() -> None:
    css = (STATIC / "visual-refresh.css").read_text(encoding="utf-8")

    mobile = css.split("@media (max-width: 700px)", 1)[1]
    assert ".rest-state-photo" in mobile
    assert "max-height: 180px;" in mobile
    assert ".workout-stage__visual--strength img" in mobile
    assert "min-height: 220px;" in mobile
