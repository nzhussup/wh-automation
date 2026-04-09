from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from powerapps_time_cli.models import MonthlyPlan


def build_payload(plan: MonthlyPlan) -> dict[str, str]:
    day_entries = [entry.model_dump(mode="json") for entry in plan.entries]
    return {"hoursjson": json.dumps(day_entries, ensure_ascii=False)}


def export_request_payload(plan: MonthlyPlan, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_payload(plan)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return output_path


def pretty_response_text(response_json: dict[str, Any]) -> str:
    return json.dumps(response_json, indent=2, ensure_ascii=False)
