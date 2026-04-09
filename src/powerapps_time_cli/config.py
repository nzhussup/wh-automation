from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from powerapps_time_cli.calculations import ValidationError
from powerapps_time_cli.models import AppConfig


def load_config(env_file: str = ".env") -> AppConfig:
    load_dotenv(env_file)

    invoke_url = os.getenv("POWERAPPS_INVOKE_URL", "").strip()
    request_url = os.getenv("POWERAPPS_REQUEST_URL", "").strip()
    if not invoke_url:
        raise ValidationError("Missing POWERAPPS_INVOKE_URL in .env/environment.")
    if not request_url:
        raise ValidationError("Missing POWERAPPS_REQUEST_URL in .env/environment.")

    extra_headers_raw = os.getenv("POWERAPPS_EXTRA_HEADERS", "")
    holiday_dates_raw = os.getenv("POWERAPPS_HOLIDAY_DATES", "")

    extra_headers: dict[str, str] = {}
    if extra_headers_raw.strip():
        try:
            parsed = json.loads(extra_headers_raw)
        except json.JSONDecodeError as exc:
            raise ValidationError("POWERAPPS_EXTRA_HEADERS must be valid JSON object") from exc

        if not isinstance(parsed, dict):
            raise ValidationError("POWERAPPS_EXTRA_HEADERS must be a JSON object")

        for key, value in parsed.items():
            extra_headers[str(key)] = str(value)

    holiday_dates = _parse_holiday_dates(holiday_dates_raw)

    return AppConfig(
        invoke_url=invoke_url,
        request_url=request_url,
        bearer_token=os.getenv("POWERAPPS_BEARER_TOKEN"),
        email=os.getenv("POWERAPPS_EMAIL"),
        origin=os.getenv("POWERAPPS_ORIGIN", "https://apps.powerapps.com"),
        referer=os.getenv("POWERAPPS_REFERER", "https://apps.powerapps.com/"),
        extra_headers=extra_headers,
        holiday_dates=holiday_dates,
    )


def ensure_env_file(path: Path) -> None:
    if path.exists():
        return

    example = """POWERAPPS_BEARER_TOKEN=
POWERAPPS_EMAIL=
POWERAPPS_INVOKE_URL=
POWERAPPS_REQUEST_URL=
POWERAPPS_ORIGIN=https://apps.powerapps.com
POWERAPPS_REFERER=https://apps.powerapps.com/
POWERAPPS_EXTRA_HEADERS={}
POWERAPPS_HOLIDAY_DATES=
"""

    path.write_text(example, encoding="utf-8")


def _parse_holiday_dates(raw: str) -> set[str]:
    values = [piece.strip() for piece in raw.split(",") if piece.strip()]
    result: set[str] = set()
    for value in values:
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise ValidationError(
                f"Invalid POWERAPPS_HOLIDAY_DATES date: {value}. Use YYYY-MM-DD."
            ) from exc
        result.add(parsed.isoformat())
    return result
