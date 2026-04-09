import pytest

from powerapps_time_cli.calendar_generation import WorkPattern, apply_override, generate_month_plan
from powerapps_time_cli.calculations import ValidationError


def test_generate_month_weekends_are_zero_target() -> None:
    pattern = WorkPattern(
        start=(8, 0),
        end=(16, 0),
        pause1_start=(13, 0),
        pause1_end=(13, 30),
        pause2_start=None,
        pause2_end=None,
        passive_travel=None,
        az_soll=7.7,
        az_soll_ot=8.0,
    )
    plan = generate_month_plan(2026, 4, "user@example.com", pattern)

    weekend_entry = next(entry for entry in plan.entries if entry.LogDate == "2026-04-04")
    assert weekend_entry.AZSoll_Decimal == 0
    assert weekend_entry.Start_Hours is None


def test_override_holiday_updates_day() -> None:
    pattern = WorkPattern(
        start=(8, 0),
        end=(16, 0),
        pause1_start=(13, 0),
        pause1_end=(13, 30),
        pause2_start=None,
        pause2_end=None,
        passive_travel=None,
        az_soll=7.7,
        az_soll_ot=8.0,
    )
    plan = generate_month_plan(2026, 4, "user@example.com", pattern)

    apply_override(plan, "2026-04-06", "holiday")

    holiday_entry = next(entry for entry in plan.entries if entry.LogDate == "2026-04-06")
    assert holiday_entry.OnLeave == "Feiertag"
    assert holiday_entry.WorkedTime_Decimal is None
    assert plan.overrides["2026-04-06"] == "holiday"


def test_generate_month_uses_auto_holidays() -> None:
    pattern = WorkPattern(
        start=(8, 0),
        end=(16, 0),
        pause1_start=(13, 0),
        pause1_end=(13, 30),
        pause2_start=None,
        pause2_end=None,
        passive_travel=None,
        az_soll=7.7,
        az_soll_ot=8.0,
    )
    plan = generate_month_plan(
        2026,
        5,
        "user@example.com",
        pattern,
        holiday_dates={"2026-05-01", "2026-05-14"},
    )

    may_first = next(entry for entry in plan.entries if entry.LogDate == "2026-05-01")
    assert may_first.OnLeave == "Feiertag"
    assert may_first.AZSoll_Decimal == 0
    assert may_first.WorkedTime_Decimal is None


def test_weekend_custom_hours_override_is_blocked() -> None:
    pattern = WorkPattern(
        start=(8, 0),
        end=(16, 0),
        pause1_start=(13, 0),
        pause1_end=(13, 30),
        pause2_start=None,
        pause2_end=None,
        passive_travel=None,
        az_soll=7.7,
        az_soll_ot=8.0,
    )
    plan = generate_month_plan(2026, 4, "user@example.com", pattern)

    with pytest.raises(ValidationError):
        apply_override(plan, "2026-04-04", "custom_hours", start="08:00", end="16:00")
