import json

from powerapps_time_cli.calendar_generation import WorkPattern, generate_month_plan
from powerapps_time_cli.payload import build_payload


def test_sharepoint_payload_uses_hoursjson() -> None:
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
    payload = build_payload(plan)

    assert set(payload.keys()) == {"hoursjson"}
    decoded = json.loads(payload["hoursjson"])
    assert isinstance(decoded, list)
    assert decoded[0]["LogDate"].startswith("2026-04-")
