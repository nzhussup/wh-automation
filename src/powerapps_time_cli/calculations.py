from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


class ValidationError(ValueError):
    """Raised when time values are invalid."""


@dataclass(frozen=True)
class TimeRange:
    start_minutes: int
    end_minutes: int


def parse_hhmm(value: str, *, allow_empty: bool = False) -> tuple[int, int] | None:
    text = value.strip()
    if allow_empty and text == "":
        return None

    try:
        parsed = datetime.strptime(text, "%H:%M")
    except ValueError as exc:
        raise ValidationError(f"Invalid time '{value}'. Use HH:MM (24h).") from exc

    return parsed.hour, parsed.minute


def to_minutes(hours: int, minutes: int) -> int:
    if not (0 <= hours <= 23 and 0 <= minutes <= 59):
        raise ValidationError("Hours must be 0..23 and minutes must be 0..59")
    return hours * 60 + minutes


def minutes_to_hm(total_minutes: int) -> tuple[int, int]:
    if total_minutes < 0:
        raise ValidationError("Duration minutes cannot be negative")
    return divmod(total_minutes, 60)


def rounded_decimal(hours_value: float) -> float:
    return round(hours_value + 1e-9, 2)


def compute_worked_time_decimal(
    start: tuple[int, int] | None,
    end: tuple[int, int] | None,
    pauses: list[tuple[tuple[int, int], tuple[int, int]]],
) -> float:
    if start is None or end is None:
        return 0.0

    start_m = to_minutes(*start)
    end_m = to_minutes(*end)
    if end_m <= start_m:
        raise ValidationError("End time must be after start time")

    pause_total = 0
    for pause_start, pause_end in pauses:
        p_start = to_minutes(*pause_start)
        p_end = to_minutes(*pause_end)
        if p_end <= p_start:
            raise ValidationError("Pause end must be after pause start")
        if p_start < start_m or p_end > end_m:
            raise ValidationError("Pauses must be within work start/end")
        pause_total += p_end - p_start

    worked_minutes = end_m - start_m - pause_total
    if worked_minutes < 0:
        raise ValidationError("Worked minutes cannot be negative")

    return rounded_decimal(worked_minutes / 60)


def compute_deltas(worked: float, az_soll: float, az_soll_ot: float) -> tuple[float, float]:
    return rounded_decimal(worked - az_soll), rounded_decimal(worked - az_soll_ot)


def parse_optional_duration(value: str) -> tuple[int, int] | None:
    return parse_hhmm(value, allow_empty=True)
