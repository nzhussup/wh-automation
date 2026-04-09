from __future__ import annotations

from pathlib import Path
import re

import typer
from rich.console import Console
from rich.table import Table

from powerapps_time_cli.calendar_generation import (
    WorkPattern,
    apply_override,
    generate_month_plan,
)
from powerapps_time_cli.calculations import ValidationError, parse_hhmm
from powerapps_time_cli.client import PowerAppsClient
from powerapps_time_cli.config import ensure_env_file, load_config
from powerapps_time_cli.models import MonthlyPlan
from powerapps_time_cli.payload import export_request_payload, pretty_response_text
from powerapps_time_cli.render import build_preview_table, summarize_plan
from powerapps_time_cli.storage import load_plan, save_plan
from powerapps_time_cli.validation import assert_valid_plan, validate_plan

app = typer.Typer(help="Power Apps monthly time-entry automation CLI")
console = Console()


@app.command()
def setup(env_file: str = ".env") -> None:
    """Create a .env template if missing and validate config parsing."""
    path = Path(env_file)
    ensure_env_file(path)
    console.print(f"[green]Config file ready:[/green] {path}")

    try:
        config = load_config(env_file)
    except ValidationError as exc:
        console.print(f"[yellow]Config not complete yet:[/yellow] {exc}")
        console.print("Fill required POWERAPPS_INVOKE_URL and POWERAPPS_REQUEST_URL in .env.")
        return

    console.print(f"Invoke URL: {config.invoke_url}")
    console.print(f"Request URL: {config.request_url}")
    console.print("Set POWERAPPS_BEARER_TOKEN manually before submit.")


@app.command("fill-month")
def fill_month(
    item_id: str | None = typer.Option(None, help="SharePoint item id to patch"),
    export_json: str | None = typer.Option(
        None, "--export", help="Export request payload JSON"
    ),
    submit_now: bool = typer.Option(
        False, "--submit", help="Submit immediately after confirmation"
    ),
    env_file: str = typer.Option(".env", help="Env file path"),
) -> None:
    """Interactive flow to create a monthly plan, preview, and optionally submit."""
    config = load_config(env_file)
    client = PowerAppsClient(config)

    selected_item_id = item_id or typer.prompt("SharePoint item id").strip()
    if selected_item_id == "":
        console.print("[red]Item id is required.[/red]")
        raise typer.Exit(code=1)

    try:
        patch_request_url = _build_patch_request_url(config.request_url, selected_item_id)
    except ValidationError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    item = _fetch_item_or_exit(client, patch_request_url)

    selected_year = _coerce_int(item.get("Year"))
    selected_month = _coerce_int(item.get("Month"))
    if selected_year is None:
        selected_year = _prompt_int("Year", default=2026, min_value=2000, max_value=2100)
    if selected_month is None:
        selected_month = _prompt_int("Month", default=1, min_value=1, max_value=12)

    item_email = _coerce_str(item.get("EmployeeMail"))
    if item_email and config.email and item_email.lower() != config.email.lower():
        console.print(
            "[red]Email mismatch:[/red] SharePoint item EmployeeMail differs from "
            "POWERAPPS_EMAIL."
        )
        console.print(f"Item email: {item_email}")
        console.print(f"Config email: {config.email}")
        raise typer.Exit(code=1)
    selected_email = item_email or config.email
    if not selected_email:
        selected_email = typer.prompt("Email")

    console.print("\n[bold]Default weekday pattern[/bold]")
    start = _prompt_required_time("Start time (HH:MM)", "08:00")
    end = _prompt_required_time("End time (HH:MM)", "16:00")
    pause1_start = _prompt_optional_time("First pause start (HH:MM, blank for none)", "13:00")
    pause1_end = _prompt_optional_time("First pause end (HH:MM, blank for none)", "13:30")
    pause2_start = _prompt_optional_time("Second pause start (HH:MM, blank for none)", "")
    pause2_end = _prompt_optional_time("Second pause end (HH:MM, blank for none)", "")
    passive_travel = _prompt_optional_time("Passive travel HH:MM (blank for none)", "")

    az_soll = _prompt_float("AZSoll_Decimal", 7.7)
    az_soll_ot = _prompt_float("AZSoll_OT_Decimal", 8.0)

    pattern = WorkPattern(
        start=start,
        end=end,
        pause1_start=pause1_start,
        pause1_end=pause1_end,
        pause2_start=pause2_start,
        pause2_end=pause2_end,
        passive_travel=passive_travel,
        az_soll=az_soll,
        az_soll_ot=az_soll_ot,
    )

    plan = generate_month_plan(
        selected_year,
        selected_month,
        selected_email,
        pattern,
        holiday_dates=config.holiday_dates,
    )

    console.print("\n[bold]Overrides[/bold]")
    _override_loop(plan)

    _display_plan(plan)
    _print_summary(plan)

    assert_valid_plan(plan)
    saved_path = save_plan(plan)
    console.print(f"\n[green]Saved plan:[/green] {saved_path}")

    if export_json:
        path = export_request_payload(
            plan,
            Path(export_json),
        )
        console.print(f"[green]Exported request payload:[/green] {path}")

    if submit_now or typer.confirm("Submit now?", default=False):
        _submit_patch_plan(plan, client, patch_request_url, item)


@app.command()
def preview(file: str | None = typer.Option(None, "--file", help="Plan file path")) -> None:
    """Render a rich preview table for a saved plan."""
    plan = load_plan(file)
    _display_plan(plan)
    _print_summary(plan)


@app.command()
def validate(file: str | None = typer.Option(None, "--file", help="Plan file path")) -> None:
    """Validate a saved plan."""
    plan = load_plan(file)
    errors = validate_plan(plan)
    if errors:
        console.print("[red]Validation failed:[/red]")
        for msg in errors:
            console.print(f"- {msg}")
        raise typer.Exit(code=1)
    console.print("[green]Plan is valid.[/green]")


@app.command()
def submit(
    file: str | None = typer.Option(None, "--file", help="Plan file path"),
    item_id: str | None = typer.Option(None, "--item-id", help="SharePoint item id to patch"),
    yes: bool = typer.Option(False, "--yes", help="Skip submit confirmation"),
    env_file: str = typer.Option(".env", help="Env file path"),
) -> None:
    """Submit a saved monthly plan to the Power Apps backend."""
    plan = load_plan(file)
    assert_valid_plan(plan)

    if not yes:
        _display_plan(plan)
        _print_summary(plan)
        if not typer.confirm("Submit this monthly request?", default=False):
            console.print("Cancelled.")
            raise typer.Exit(code=0)

    config = load_config(env_file)
    client = PowerAppsClient(config)
    selected_item_id = item_id or typer.prompt("SharePoint item id").strip()
    if selected_item_id == "":
        console.print("[red]Item id is required.[/red]")
        raise typer.Exit(code=1)
    try:
        patch_request_url = _build_patch_request_url(config.request_url, selected_item_id)
    except ValidationError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    item = _fetch_item_or_exit(client, patch_request_url)
    _submit_patch_plan(plan, client, patch_request_url, item)


def _submit_patch_plan(
    plan: MonthlyPlan,
    client: PowerAppsClient,
    patch_request_url: str,
    item: dict[str, object],
) -> None:
    item_email = _coerce_str(item.get("EmployeeMail"))
    if item_email and item_email.lower() != plan.email.lower():
        console.print(
            "[red]Email mismatch:[/red] Saved plan email differs from SharePoint "
            "item EmployeeMail."
        )
        console.print(f"Plan email: {plan.email}")
        console.print(f"Item email: {item_email}")
        raise typer.Exit(code=1)

    default_if_match = _coerce_str(item.get("@odata.etag")) or "*"
    if_match = typer.prompt('If-Match value ("*" or ETag like "\\"3\\"")', default=default_if_match)
    try:
        result = client.submit_patch(plan, patch_request_url, if_match)
    except Exception as exc:
        console.print(f"[red]PATCH submit failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print("[green]PATCH submit succeeded.[/green]")
    console.print(pretty_response_text(result))


def _fetch_item_or_exit(client: PowerAppsClient, patch_request_url: str) -> dict[str, object]:
    try:
        data = client.fetch_item(patch_request_url)
    except Exception as exc:
        console.print(f"[red]Failed to load SharePoint item metadata:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    return data


def _build_patch_request_url(base_request_url: str, item_id: str) -> str:
    if "/apim/sharepointonline/" not in base_request_url:
        raise ValidationError(
            "POWERAPPS_REQUEST_URL must be a SharePoint connector path ending with /items/<id> "
            "or /items for patch mode."
        )
    if "/items/" in base_request_url:
        return re.sub(r"/items/[^/]+$", f"/items/{item_id}", base_request_url)
    if base_request_url.endswith("/items"):
        return f"{base_request_url}/{item_id}"
    return f"{base_request_url.rstrip('/')}/{item_id}"


def _coerce_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None


def _coerce_str(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _override_loop(plan: MonthlyPlan) -> None:
    while True:
        date_text = typer.prompt("Override date YYYY-MM-DD (blank to finish)", default="").strip()
        if date_text == "":
            return

        option = typer.prompt(
            "Type (leave, holiday, custom-hours, custom-pauses, custom-pr, no-entry)",
            default="custom-hours",
        ).strip()

        try:
            if option == "leave":
                label = typer.prompt("Leave label", default="Leave")
                apply_override(plan, date_text, "leave", label=label)
            elif option == "holiday":
                apply_override(plan, date_text, "holiday")
            elif option == "custom-hours":
                start = typer.prompt("Start HH:MM", default="08:00")
                end = typer.prompt("End HH:MM", default="16:00")
                pause1_start = typer.prompt("Pause1 start HH:MM (blank keep)", default="")
                pause1_end = typer.prompt("Pause1 end HH:MM (blank keep)", default="")
                pause2_start = typer.prompt("Pause2 start HH:MM (blank keep)", default="")
                pause2_end = typer.prompt("Pause2 end HH:MM (blank keep)", default="")
                passive_travel = typer.prompt("Passive travel HH:MM (blank keep)", default="")
                payload: dict[str, str] = {
                    "start": start,
                    "end": end,
                }
                if pause1_start != "":
                    payload["pause1_start"] = pause1_start
                if pause1_end != "":
                    payload["pause1_end"] = pause1_end
                if pause2_start != "":
                    payload["pause2_start"] = pause2_start
                if pause2_end != "":
                    payload["pause2_end"] = pause2_end
                if passive_travel != "":
                    payload["passive_travel"] = passive_travel
                apply_override(plan, date_text, "custom_hours", **payload)
            elif option == "custom-pauses":
                apply_override(
                    plan,
                    date_text,
                    "custom_pauses",
                    pause1_start=typer.prompt("Pause1 start HH:MM (blank clears)", default=""),
                    pause1_end=typer.prompt("Pause1 end HH:MM (blank clears)", default=""),
                    pause2_start=typer.prompt("Pause2 start HH:MM (blank clears)", default=""),
                    pause2_end=typer.prompt("Pause2 end HH:MM (blank clears)", default=""),
                )
            elif option == "custom-pr":
                apply_override(
                    plan,
                    date_text,
                    "custom_passive_travel",
                    passive_travel=typer.prompt("Passive travel HH:MM (blank clears)", default=""),
                )
            elif option == "no-entry":
                apply_override(plan, date_text, "no_entry")
            else:
                console.print("[yellow]Unknown override type.[/yellow]")
                continue

            console.print(f"[green]Applied override:[/green] {date_text} -> {option}")
        except ValidationError as exc:
            console.print(f"[red]Override failed:[/red] {exc}")


def _display_plan(plan: MonthlyPlan) -> None:
    table = build_preview_table(plan)
    console.print(table)


def _print_summary(plan: MonthlyPlan) -> None:
    summary = summarize_plan(plan)
    table = Table(title="Summary")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    for key, value in summary.items():
        table.add_row(key, str(value))
    console.print(table)


def _prompt_int(label: str, *, default: int, min_value: int, max_value: int) -> int:
    while True:
        value = typer.prompt(label, default=default)
        try:
            parsed = int(value)
        except ValueError:
            console.print("[red]Enter a valid integer.[/red]")
            continue
        if not min_value <= parsed <= max_value:
            console.print(f"[red]Must be between {min_value} and {max_value}.[/red]")
            continue
        return parsed


def _prompt_float(label: str, default: float) -> float:
    while True:
        value = typer.prompt(label, default=f"{default}")
        try:
            return round(float(value), 2)
        except ValueError:
            console.print("[red]Enter a valid decimal value.[/red]")


def _prompt_required_time(label: str, default: str) -> tuple[int, int]:
    while True:
        value = typer.prompt(label, default=default)
        try:
            parsed = parse_hhmm(value)
            if parsed is None:
                console.print("[red]Time is required.[/red]")
                continue
            return parsed
        except ValidationError as exc:
            console.print(f"[red]{exc}[/red]")


def _prompt_optional_time(label: str, default: str) -> tuple[int, int] | None:
    while True:
        value = typer.prompt(label, default=default)
        try:
            return parse_hhmm(value, allow_empty=True)
        except ValidationError as exc:
            console.print(f"[red]{exc}[/red]")


if __name__ == "__main__":
    app()
