from decimal import Decimal

from hwa.read_models.training_analytics import estimate_epley_1rm


def test_epley_estimate_uses_recorded_load_basis_and_rounds_to_tenth() -> None:
    assert estimate_epley_1rm(Decimal("10"), 10) == Decimal("13.3")
    assert estimate_epley_1rm(Decimal("6"), 12) == Decimal("8.4")


def test_epley_estimate_handles_single_and_rejects_noisy_or_invalid_sets() -> None:
    assert estimate_epley_1rm(Decimal("10"), 1) == Decimal("10.0")
    assert estimate_epley_1rm(Decimal("10"), 16) is None
    assert estimate_epley_1rm(Decimal("0"), 10) is None
    assert estimate_epley_1rm(Decimal("10"), 0) is None
