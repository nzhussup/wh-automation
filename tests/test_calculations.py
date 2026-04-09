import pytest

from powerapps_time_cli.calculations import (
    ValidationError,
    compute_deltas,
    compute_worked_time_decimal,
)


def test_compute_worked_time_decimal_with_two_pauses() -> None:
    worked = compute_worked_time_decimal(
        (8, 0),
        (16, 0),
        [((13, 0), (13, 30)), ((15, 0), (15, 30))],
    )
    assert worked == 7.0


def test_compute_deltas_rounding() -> None:
    delta, delta_ot = compute_deltas(7.03, 7.7, 8.0)
    assert delta == -0.67
    assert delta_ot == -0.97


def test_invalid_pause_raises() -> None:
    with pytest.raises(ValidationError):
        compute_worked_time_decimal((8, 0), (16, 0), [((13, 30), (13, 0))])
