from dataclasses import replace

from hwa.domain.identity import PersonContext
from hwa.web.context import NAV_ITEMS, build_page_context


def _person() -> PersonContext:
    return PersonContext(
        hwa_person_id="hwa-kris",
        pep_person_id="person_a",
        health_profile_id="kris",
        menu_person_id="person_1",
        presentation_profile="male",
        display_name="Kris",
    )


def test_product_navigation_has_exactly_five_approved_surfaces() -> None:
    assert [(item.key, item.path) for item in NAV_ITEMS] == [
        ("today", "/"),
        ("workout", "/workout"),
        ("progress", "/progress"),
        ("library", "/library"),
        ("settings", "/settings"),
    ]


def test_page_context_is_person_scoped_and_marks_only_active_navigation() -> None:
    context = build_page_context(_person(), "progress")

    assert context.display_name == "Kris"
    assert context.presentation_profile == "male"
    assert context.active_nav == "progress"
    assert [item.key for item in context.navigation if item.active] == ["progress"]

    # Public page context must not expose cross-system authority identifiers.
    assert not hasattr(context, "hwa_person_id")
    assert not hasattr(context, "pep_person_id")
    assert not hasattr(context, "health_profile_id")
    assert not hasattr(context, "menu_person_id")


def test_page_context_rejects_unknown_navigation_key() -> None:
    try:
        build_page_context(_person(), "admin")
    except ValueError as exc:
        assert str(exc) == "UNKNOWN_NAVIGATION_SURFACE"
    else:
        raise AssertionError("unknown navigation surface should fail closed")


def test_page_context_changes_only_from_resolved_person() -> None:
    kris = _person()
    kirsty = replace(
        kris,
        hwa_person_id="hwa-kirsty",
        display_name="Kirsty",
        presentation_profile="female",
    )

    assert build_page_context(kris, "today").display_name == "Kris"
    assert build_page_context(kirsty, "today").display_name == "Kirsty"
