from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


OverrideType = Literal[
    "default",
    "weekend",
    "holiday",
    "leave",
    "custom_hours",
    "custom_pauses",
    "custom_passive_travel",
    "no_entry",
]


class DayEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    AZSoll_Decimal: float
    AZSoll_OT_Decimal: float
    End_Hours: int | None = None
    End_Minutes: int | None = None
    LogDate: str
    OnLeave: str | None = None
    PR_Hours: int | None = None
    PR_Minutes: int | None = None
    PauseEnd_Hours: int | None = None
    PauseEnd_Hours_1: int | None = None
    PauseEnd_Minutes: int | None = None
    PauseEnd_Minutes_1: int | None = None
    PauseStart_Hours: int | None = None
    PauseStart_Hours_1: int | None = None
    PauseStart_Minutes: int | None = None
    PauseStart_Minutes_1: int | None = None
    Start_Hours: int | None = None
    Start_Minutes: int | None = None
    WorkedTime_Decimal: float | None = None
    deltaAZ_Decimal: float | None = None
    deltaAZ_OT_Decimal: float | None = None
    freigabeStatus: str | None = None
    freigabeTyp: str | None = None

    @field_validator(
        "End_Hours",
        "End_Minutes",
        "PR_Hours",
        "PR_Minutes",
        "PauseEnd_Hours",
        "PauseEnd_Hours_1",
        "PauseEnd_Minutes",
        "PauseEnd_Minutes_1",
        "PauseStart_Hours",
        "PauseStart_Hours_1",
        "PauseStart_Minutes",
        "PauseStart_Minutes_1",
        "Start_Hours",
        "Start_Minutes",
    )
    @classmethod
    def validate_time_component(cls, value: int | None, info: object) -> int | None:
        if value is None:
            return None
        field_name = getattr(info, "field_name", "time value")
        if "Hours" in field_name and not (0 <= value <= 23):
            raise ValueError(f"{field_name} must be between 0 and 23")
        if "Minutes" in field_name and not (0 <= value <= 59):
            raise ValueError(f"{field_name} must be between 0 and 59")
        return value


class MonthlyPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    year: int
    month: int
    entries: list[DayEntry]
    overrides: dict[str, OverrideType] = Field(default_factory=dict)


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invoke_url: str
    request_url: str
    bearer_token: str | None = None
    email: str | None = None
    origin: str = "https://apps.powerapps.com"
    referer: str = "https://apps.powerapps.com/"
    extra_headers: dict[str, str] = Field(default_factory=dict)
    holiday_dates: set[str] = Field(default_factory=set)
