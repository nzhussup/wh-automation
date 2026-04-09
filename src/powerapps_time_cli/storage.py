from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError as PydanticValidationError

from powerapps_time_cli.calculations import ValidationError
from powerapps_time_cli.models import MonthlyPlan

STATE_DIR = Path(".timeentry")
LATEST_FILE = STATE_DIR / "latest.json"


def save_plan(plan: MonthlyPlan) -> Path:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    monthly_path = STATE_DIR / f"{plan.year}-{plan.month:02d}.json"
    payload = plan.model_dump(mode="json")
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    monthly_path.write_text(text, encoding="utf-8")
    LATEST_FILE.write_text(text, encoding="utf-8")
    return monthly_path


def load_plan(path: str | None = None) -> MonthlyPlan:
    target = Path(path) if path else LATEST_FILE
    if not target.exists():
        raise ValidationError(
            f"Plan file not found: {target}. Run 'fill-month' first or pass --file path."
        )

    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        return MonthlyPlan.model_validate(data)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"Invalid JSON in {target}") from exc
    except PydanticValidationError as exc:
        raise ValidationError(f"Invalid plan schema in {target}: {exc}") from exc
