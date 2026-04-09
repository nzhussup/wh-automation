from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date

from powerapps_time_cli.calculations import (
    ValidationError,
    compute_deltas,
    compute_worked_time_decimal,
    parse_hhmm,
)
from powerapps_time_cli.models import DayEntry, MonthlyPlan, OverrideType


@dataclass(frozen=True)
class WorkPattern:
    start: tuple[int, int] | None
    end: tuple[int, int] | None
    pause1_start: tuple[int, int] | None
    pause1_end: tuple[int, int] | None
    pause2_start: tuple[int, int] | None
    pause2_end: tuple[int, int] | None
    passive_travel: tuple[int, int] | None
    az_soll: float
    az_soll_ot: float


def _pauses_from_pattern(pattern: WorkPattern) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    pauses: list[tuple[tuple[int, int], tuple[int, int]]] = []
    if pattern.pause1_start is not None and pattern.pause1_end is not None:
        pauses.append((pattern.pause1_start, pattern.pause1_end))
    if pattern.pause2_start is not None and pattern.pause2_end is not None:
        pauses.append((pattern.pause2_start, pattern.pause2_end))
    return pauses


def _build_workday_entry(log_date: str, pattern: WorkPattern) -> DayEntry:
    pauses = _pauses_from_pattern(pattern)
    worked = compute_worked_time_decimal(pattern.start, pattern.end, pauses)
    delta, delta_ot = compute_deltas(worked, pattern.az_soll, pattern.az_soll_ot)

    return DayEntry(
        AZSoll_Decimal=pattern.az_soll,
        AZSoll_OT_Decimal=pattern.az_soll_ot,
        End_Hours=pattern.end[0] if pattern.end else None,
        End_Minutes=pattern.end[1] if pattern.end else None,
        LogDate=log_date,
        OnLeave=None,
        PR_Hours=pattern.passive_travel[0] if pattern.passive_travel else None,
        PR_Minutes=pattern.passive_travel[1] if pattern.passive_travel else None,
        PauseEnd_Hours=pattern.pause1_end[0] if pattern.pause1_end else None,
        PauseEnd_Hours_1=pattern.pause2_end[0] if pattern.pause2_end else None,
        PauseEnd_Minutes=pattern.pause1_end[1] if pattern.pause1_end else None,
        PauseEnd_Minutes_1=pattern.pause2_end[1] if pattern.pause2_end else None,
        PauseStart_Hours=pattern.pause1_start[0] if pattern.pause1_start else None,
        PauseStart_Hours_1=pattern.pause2_start[0] if pattern.pause2_start else None,
        PauseStart_Minutes=pattern.pause1_start[1] if pattern.pause1_start else None,
        PauseStart_Minutes_1=pattern.pause2_start[1] if pattern.pause2_start else None,
        Start_Hours=pattern.start[0] if pattern.start else None,
        Start_Minutes=pattern.start[1] if pattern.start else None,
        WorkedTime_Decimal=worked,
        deltaAZ_Decimal=delta,
        deltaAZ_OT_Decimal=delta_ot,
    )


def _build_empty_day(log_date: str, az_soll: float = 0.0, az_soll_ot: float = 0.0) -> DayEntry:
    return DayEntry(
        AZSoll_Decimal=az_soll,
        AZSoll_OT_Decimal=az_soll_ot,
        End_Hours=None,
        End_Minutes=None,
        LogDate=log_date,
        OnLeave=None,
        PR_Hours=None,
        PR_Minutes=None,
        PauseEnd_Hours=None,
        PauseEnd_Hours_1=None,
        PauseEnd_Minutes=None,
        PauseEnd_Minutes_1=None,
        PauseStart_Hours=None,
        PauseStart_Hours_1=None,
        PauseStart_Minutes=None,
        PauseStart_Minutes_1=None,
        Start_Hours=None,
        Start_Minutes=None,
        WorkedTime_Decimal=None,
        deltaAZ_Decimal=None,
        deltaAZ_OT_Decimal=None,
    )


def generate_month_plan(
    year: int,
    month: int,
    email: str,
    pattern: WorkPattern,
    holiday_dates: set[str] | None = None,
) -> MonthlyPlan:
    _, days_in_month = calendar.monthrange(year, month)
    entries: list[DayEntry] = []
    overrides: dict[str, OverrideType] = {}
    holidays = holiday_dates or set()

    for day in range(1, days_in_month + 1):
        current = date(year, month, day)
        log_date = current.isoformat()
        if log_date in holidays:
            holiday = _build_empty_day(log_date, az_soll=0.0, az_soll_ot=0.0)
            holiday.OnLeave = "Feiertag"
            entries.append(holiday)
            overrides[log_date] = "holiday"
            continue
        if current.weekday() >= 5:
            entries.append(_build_empty_day(log_date, az_soll=0.0, az_soll_ot=0.0))
            overrides[log_date] = "weekend"
        else:
            entries.append(_build_workday_entry(log_date, pattern))
            overrides[log_date] = "default"

    return MonthlyPlan(email=email, year=year, month=month, entries=entries, overrides=overrides)


def _find_entry(plan: MonthlyPlan, date_text: str) -> DayEntry:
    for entry in plan.entries:
        if entry.LogDate == date_text:
            return entry
    raise ValidationError(f"Date {date_text} not found in current plan")


def _require_month_date(plan: MonthlyPlan, date_text: str) -> None:
    try:
        parsed = date.fromisoformat(date_text)
    except ValueError as exc:
        raise ValidationError("Date must be in YYYY-MM-DD format") from exc

    if parsed.year != plan.year or parsed.month != plan.month:
        raise ValidationError(f"Date {date_text} is not in {plan.year}-{plan.month:02d}")


def apply_override(
    plan: MonthlyPlan,
    date_text: str,
    override_type: OverrideType,
    **kwargs: object,
) -> None:
    _require_month_date(plan, date_text)
    entry = _find_entry(plan, date_text)
    is_weekend = date.fromisoformat(date_text).weekday() >= 5

    if override_type == "holiday":
        empty = _build_empty_day(date_text, az_soll=0.0, az_soll_ot=0.0)
        empty.OnLeave = "Feiertag"
        _replace_entry(plan, date_text, empty)
    elif override_type == "leave":
        leave_label = str(kwargs.get("label", "Leave"))
        empty = _build_empty_day(date_text, az_soll=0.0, az_soll_ot=0.0)
        empty.OnLeave = leave_label
        _replace_entry(plan, date_text, empty)
    elif override_type == "no_entry":
        empty = _build_empty_day(
            date_text,
            az_soll=entry.AZSoll_Decimal,
            az_soll_ot=entry.AZSoll_OT_Decimal,
        )
        _replace_entry(plan, date_text, empty)
    elif override_type == "custom_hours":
        if is_weekend:
            raise ValidationError("Weekend work entry is blocked for this flow.")
        _apply_custom_hours(entry, kwargs)
    elif override_type == "custom_pauses":
        if is_weekend:
            raise ValidationError("Weekend work entry is blocked for this flow.")
        _apply_custom_pauses(entry, kwargs)
    elif override_type == "custom_passive_travel":
        if is_weekend:
            raise ValidationError("Weekend work entry is blocked for this flow.")
        _apply_custom_passive_travel(entry, kwargs)
    else:
        raise ValidationError(f"Unsupported override type: {override_type}")

    plan.overrides[date_text] = override_type


def _replace_entry(plan: MonthlyPlan, date_text: str, replacement: DayEntry) -> None:
    for idx, current in enumerate(plan.entries):
        if current.LogDate == date_text:
            plan.entries[idx] = replacement
            return
    raise ValidationError(f"Date {date_text} not found in plan")


def _entry_pauses(entry: DayEntry) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    pauses: list[tuple[tuple[int, int], tuple[int, int]]] = []
    if (
        entry.PauseStart_Hours is not None
        and entry.PauseStart_Minutes is not None
        and entry.PauseEnd_Hours is not None
        and entry.PauseEnd_Minutes is not None
    ):
        pauses.append(
            (
                (entry.PauseStart_Hours, entry.PauseStart_Minutes),
                (entry.PauseEnd_Hours, entry.PauseEnd_Minutes),
            )
        )
    if (
        entry.PauseStart_Hours_1 is not None
        and entry.PauseStart_Minutes_1 is not None
        and entry.PauseEnd_Hours_1 is not None
        and entry.PauseEnd_Minutes_1 is not None
    ):
        pauses.append(
            (
                (entry.PauseStart_Hours_1, entry.PauseStart_Minutes_1),
                (entry.PauseEnd_Hours_1, entry.PauseEnd_Minutes_1),
            )
        )
    return pauses


def _recompute_entry(entry: DayEntry) -> None:
    start = (
        (entry.Start_Hours, entry.Start_Minutes)
        if entry.Start_Hours is not None and entry.Start_Minutes is not None
        else None
    )
    end = (
        (entry.End_Hours, entry.End_Minutes)
        if entry.End_Hours is not None and entry.End_Minutes is not None
        else None
    )
    worked = compute_worked_time_decimal(start, end, _entry_pauses(entry))
    entry.WorkedTime_Decimal = worked
    entry.deltaAZ_Decimal, entry.deltaAZ_OT_Decimal = compute_deltas(
        worked, entry.AZSoll_Decimal, entry.AZSoll_OT_Decimal
    )


def _apply_custom_hours(entry: DayEntry, values: dict[str, object]) -> None:
    start = values.get("start")
    end = values.get("end")
    if not isinstance(start, str) or not isinstance(end, str):
        raise ValidationError("custom_hours requires 'start' and 'end' (HH:MM)")

    start_hm = parse_hhmm(start)
    end_hm = parse_hhmm(end)
    if start_hm is None or end_hm is None:
        raise ValidationError("Start and end must not be empty")

    entry.Start_Hours, entry.Start_Minutes = start_hm
    entry.End_Hours, entry.End_Minutes = end_hm
    entry.OnLeave = None

    _apply_custom_pauses(entry, values, recompute=False)
    _apply_custom_passive_travel(entry, values, recompute=False)
    _recompute_entry(entry)


def _apply_custom_pauses(
    entry: DayEntry,
    values: dict[str, object],
    *,
    recompute: bool = True,
) -> None:
    mapping = {
        "pause1_start": ("PauseStart_Hours", "PauseStart_Minutes"),
        "pause1_end": ("PauseEnd_Hours", "PauseEnd_Minutes"),
        "pause2_start": ("PauseStart_Hours_1", "PauseStart_Minutes_1"),
        "pause2_end": ("PauseEnd_Hours_1", "PauseEnd_Minutes_1"),
    }

    for key, attrs in mapping.items():
        raw = values.get(key)
        if raw is None:
            continue
        if not isinstance(raw, str):
            raise ValidationError(f"{key} must be string HH:MM or empty")
        parsed = parse_hhmm(raw, allow_empty=True)
        if parsed is None:
            setattr(entry, attrs[0], None)
            setattr(entry, attrs[1], None)
        else:
            setattr(entry, attrs[0], parsed[0])
            setattr(entry, attrs[1], parsed[1])

    if recompute:
        _recompute_entry(entry)


def _apply_custom_passive_travel(
    entry: DayEntry, values: dict[str, object], *, recompute: bool = True
) -> None:
    raw = values.get("passive_travel")
    if raw is None:
        if recompute:
            _recompute_entry(entry)
        return
    if not isinstance(raw, str):
        raise ValidationError("passive_travel must be string HH:MM or empty")

    parsed = parse_hhmm(raw, allow_empty=True)
    if parsed is None:
        entry.PR_Hours = None
        entry.PR_Minutes = None
    else:
        entry.PR_Hours, entry.PR_Minutes = parsed

    if recompute:
        _recompute_entry(entry)
