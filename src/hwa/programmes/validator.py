"""Whole-week governance validation for approved programme content."""

from hwa.programmes.schema import ProgrammeWeekDocument


class ProgrammeValidationError(ValueError):
    """An approved programme document violates whole-week governance."""


def _require_unique_sequences(
    *,
    day_number: int,
    kind: str,
    sequences: tuple[int, ...],
) -> None:
    if len(sequences) != len(set(sequences)):
        raise ProgrammeValidationError(
            f"day {day_number} contains duplicate {kind} sequence values"
        )


def validate_programme_week(document: ProgrammeWeekDocument) -> ProgrammeWeekDocument:
    """Validate completeness and references without generating missing content."""

    if len(document.days) != 4:
        raise ProgrammeValidationError(
            "an approved programme week must contain exactly four training days"
        )

    day_numbers = [day.day_number for day in document.days]
    if sorted(day_numbers) != [1, 2, 3, 4]:
        raise ProgrammeValidationError(
            "an approved programme week must contain unique day numbers 1, 2, 3 and 4"
        )

    strength_refs: set[tuple[int, str]] = set()
    for day in document.days:
        if day.programme_id != document.programme_id:
            raise ProgrammeValidationError(
                f"day {day.day_number} programme_id does not match week"
            )
        if day.week_number != document.week_number:
            raise ProgrammeValidationError(
                f"day {day.day_number} week_number does not match week"
            )
        if not day.strength and not day.cardio:
            raise ProgrammeValidationError(
                f"day {day.day_number} has no approved workout content"
            )

        _require_unique_sequences(
            day_number=day.day_number,
            kind="strength",
            sequences=tuple(item.sequence for item in day.strength),
        )
        _require_unique_sequences(
            day_number=day.day_number,
            kind="cardio",
            sequences=tuple(item.sequence for item in day.cardio),
        )
        strength_refs.update(
            (day.day_number, item.exercise_id) for item in day.strength
        )

    for canonical_key, overrides in document.person_overrides.items():
        if not canonical_key.strip():
            raise ProgrammeValidationError("person override key cannot be blank")
        seen: set[tuple[int, str]] = set()
        for override in overrides:
            reference = (override.day_number, override.exercise_id)
            if reference not in strength_refs:
                raise ProgrammeValidationError(
                    "person override references an unknown day/exercise: "
                    f"{canonical_key} day {override.day_number} {override.exercise_id}"
                )
            if reference in seen:
                raise ProgrammeValidationError(
                    "person override contains a duplicate day/exercise reference: "
                    f"{canonical_key} day {override.day_number} {override.exercise_id}"
                )
            seen.add(reference)

    return document
