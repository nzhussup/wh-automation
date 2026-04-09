from __future__ import annotations

from datetime import date

from rich.table import Table

from powerapps_time_cli.models import MonthlyPlan


def build_preview_table(plan: MonthlyPlan) -> Table:
    table = Table(title=f"Time Entries {plan.year}-{plan.month:02d}")
    table.add_column("Date")
    table.add_column("Type")
    table.add_column("Start")
    table.add_column("End")
    table.add_column("Worked", justify="right")
    table.add_column("AZSoll", justify="right")
    table.add_column("Delta", justify="right")
    table.add_column("Leave")

    for entry in plan.entries:
        entry_type = plan.overrides.get(entry.LogDate, "default")
        table.add_row(
            entry.LogDate,
            entry_type,
            _format_hm(entry.Start_Hours, entry.Start_Minutes),
            _format_hm(entry.End_Hours, entry.End_Minutes),
            _format_decimal(entry.WorkedTime_Decimal),
            f"{entry.AZSoll_Decimal:.2f}",
            _format_decimal(entry.deltaAZ_Decimal),
            entry.OnLeave or "",
        )

    return table


def summarize_plan(plan: MonthlyPlan) -> dict[str, int]:
    weekends = 0
    holidays = 0
    leave_days = 0
    custom_override_days = 0
    working_days = 0

    for entry in plan.entries:
        kind = plan.overrides.get(entry.LogDate, "default")
        weekday = date.fromisoformat(entry.LogDate).weekday()
        if weekday >= 5:
            weekends += 1

        if kind == "holiday":
            holidays += 1
        elif kind == "leave":
            leave_days += 1
        elif kind in {"custom_hours", "custom_pauses", "custom_passive_travel", "no_entry"}:
            custom_override_days += 1

        if entry.AZSoll_Decimal > 0 or entry.Start_Hours is not None or entry.OnLeave is not None:
            working_days += 1

    return {
        "working_days": working_days,
        "weekends": weekends,
        "holidays": holidays,
        "leave_days": leave_days,
        "custom_override_days": custom_override_days,
        "total_days": len(plan.entries),
    }


def _format_hm(hours: int | None, minutes: int | None) -> str:
    if hours is None or minutes is None:
        return ""
    return f"{hours:02d}:{minutes:02d}"


def _format_decimal(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.2f}"
