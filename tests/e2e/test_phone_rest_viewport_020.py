from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "src" / "hwa" / "web" / "static"


def test_020_phone_rest_uses_compact_overlay_photo_layout() -> None:
    css = (STATIC / "visual-refresh.css").read_text(encoding="utf-8")
    mobile = css.split("@media (max-width: 700px)", 1)[1]

    assert ".main-rest-panel {" in mobile
    rest = mobile.split(".main-rest-panel {", 1)[1].split("}", 1)[0]
    assert "position: relative;" in rest
    assert "min-height: 430px !important;" in rest
    assert 'grid-template-areas:' in rest
    assert '"eyebrow"' in rest
    assert '"ring"' in rest
    assert '"next"' in rest
    assert '"actions"' in rest

    photo = mobile.split(".rest-state-photo {", 1)[1].split("}", 1)[0]
    assert "position: absolute;" in photo
    assert "inset: 0;" in photo
    assert "max-height: none;" in photo

    image = mobile.split(".rest-state-photo img {", 1)[1].split("}", 1)[0]
    assert "height: 100%;" in image
    assert "max-height: none;" in image

    ring = mobile.split(".main-rest-ring {", 1)[1].split("}", 1)[0]
    assert "width: 136px;" in ring
    assert "height: 136px;" in ring


def test_020_phone_rest_content_sits_above_recovery_photo() -> None:
    css = (STATIC / "visual-refresh.css").read_text(encoding="utf-8")
    mobile = css.split("@media (max-width: 700px)", 1)[1]

    assert ".main-rest-panel > :not(.rest-state-photo)" in mobile
    content = mobile.split(
        ".main-rest-panel > :not(.rest-state-photo)", 1
    )[1].split("}", 1)[0]
    assert "position: relative;" in content
    assert "z-index: 1;" in content
