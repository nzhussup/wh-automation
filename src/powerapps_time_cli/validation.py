from __future__ import annotations

from datetime import date

from powerapps_time_cli.calculations import ValidationError
from powerapps_time_cli.models import MonthlyPlan


def validate_plan(plan: MonthlyPlan) -> list[str]:
    errors: list[str] = []

    for entry in plan.entries:
        try:
            log_date = date.fromisoformat(entry.LogDate)
        except ValueError:
            errors.append(f"Invalid LogDate format: {entry.LogDate}")
            continue

        if log_date.year != plan.year or log_date.month != plan.month:
            errors.append(f"Date out of selected month: {entry.LogDate}")

        _check_start_end(
            entry.Start_Hours,
            entry.Start_Minutes,
            entry.End_Hours,
            entry.End_Minutes,
            entry.LogDate,
            errors,
        )
        _check_pause(
            entry.PauseStart_Hours,
            entry.PauseStart_Minutes,
            entry.PauseEnd_Hours,
            entry.PauseEnd_Minutes,
            entry.LogDate,
            "pause1",
            errors,
        )
        _check_pause(
            entry.PauseStart_Hours_1,
            entry.PauseStart_Minutes_1,
            entry.PauseEnd_Hours_1,
            entry.PauseEnd_Minutes_1,
            entry.LogDate,
            "pause2",
            errors,
        )

    if len({entry.LogDate for entry in plan.entries}) != len(plan.entries):
        errors.append("Duplicate LogDate entries detected")

    return errors


def assert_valid_plan(plan: MonthlyPlan) -> None:
    errors = validate_plan(plan)
    if errors:
        joined = "\n".join(f"- {message}" for message in errors)
        raise ValidationError(f"Plan validation failed:\n{joined}")


def _check_start_end(
    start_h: int | None,
    start_m: int | None,
    end_h: int | None,
    end_m: int | None,
    log_date: str,
    errors: list[str],
) -> None:
    has_start = start_h is not None and start_m is not None
    has_end = end_h is not None and end_m is not None
    if has_start != has_end:
        errors.append(f"{log_date}: start/end must be both set or both null")
        return
    if not has_start:
        return

    start_total = start_h * 60 + start_m
    end_total = end_h * 60 + end_m
    if end_total <= start_total:
        errors.append(f"{log_date}: end must be after start")


def _check_pause(
    start_h: int | None,
    start_m: int | None,
    end_h: int | None,
    end_m: int | None,
    log_date: str,
    label: str,
    errors: list[str],
) -> None:
    has_start = start_h is not None and start_m is not None
    has_end = end_h is not None and end_m is not None
    if has_start != has_end:
        errors.append(f"{log_date}: {label} start/end must be both set or both null")
        return
    if not has_start:
        return

    start_total = start_h * 60 + start_m
    end_total = end_h * 60 + end_m
    if end_total <= start_total:
        errors.append(f"{log_date}: {label} end must be after {label} start")
