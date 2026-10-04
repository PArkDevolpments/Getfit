"""Presentation-only page context for the Getfit product shell."""

from dataclasses import dataclass, replace

from hwa.domain.identity import PersonContext


@dataclass(frozen=True, slots=True)
class NavigationItem:
    """One approved product surface exposed in navigation."""

    key: str
    label: str
    path: str
    active: bool = False


NAV_ITEMS = (
    NavigationItem("today", "Today", "/"),
    NavigationItem("plan", "Plan", "/plan"),
    NavigationItem("workout", "Workout", "/workout"),
    NavigationItem("progress", "Progress", "/progress"),
    NavigationItem("more", "More", "/more"),
)


@dataclass(frozen=True, slots=True)
class PageContext:
    """Safe browser context derived from the already-resolved trusted person."""

    display_name: str
    presentation_profile: str
    active_nav: str
    navigation: tuple[NavigationItem, ...]


def build_page_context(person: PersonContext, active_nav: str) -> PageContext:
    """Build presentation context without leaking cross-system identity keys."""

    if active_nav not in {item.key for item in NAV_ITEMS}:
        raise ValueError("UNKNOWN_NAVIGATION_SURFACE")
    navigation = tuple(replace(item, active=item.key == active_nav) for item in NAV_ITEMS)
    return PageContext(
        display_name=person.display_name,
        presentation_profile=person.presentation_profile,
        active_nav=active_nav,
        navigation=navigation,
    )
