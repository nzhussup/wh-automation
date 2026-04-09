# Power Apps Monthly Time Entry CLI

Interactive Python CLI (Typer + Rich) to generate and PATCH monthly time-entry `hoursjson` into an existing SharePoint item through the Power Apps invoke endpoint.

## Why This Exists

I built this because I got fed up with the horrible UX of the internal time-tracking app.  
There was no reliable bulk-entry option, so this CLI lets me prepare and submit a whole month in one flow.

## Features

- Poetry-managed project with typed modular code under `src/`
- Patch-first workflow: item id is asked first
- Year/month/email auto-detected from the selected SharePoint item (fallback prompts only if missing)
- Rich preview + validation before submit
- Payload export for debugging (`{"hoursjson":"[...]"}`)
- Config via `.env` only (no hardcoded secrets)

## Setup

```bash
poetry install
cp .env.example .env
poetry run powerapps-time setup
```

## Environment

```env
POWERAPPS_BEARER_TOKEN=...paste from authenticated browser session...
POWERAPPS_EMAIL=your.name@company.com
POWERAPPS_INVOKE_URL=https://<your-env-id>.02.common.europe002.azure-apihub.net/invoke
POWERAPPS_REQUEST_URL=/apim/sharepointonline/<connection-id>/datasets/<site-encoded>/tables/<list-id>/items/<item-id>
POWERAPPS_ORIGIN=https://apps.powerapps.com
POWERAPPS_REFERER=https://apps.powerapps.com/
POWERAPPS_EXTRA_HEADERS={"x-ms-client-app-id":"/providers/Microsoft.PowerApps/apps/<app-id>","x-ms-client-environment-id":"/providers/Microsoft.PowerApps/environments/<env-id>","x-ms-client-object-id":"<object-id>","x-ms-client-request-id":"<request-id>","x-ms-client-session-id":"<session-id>","x-ms-client-tenant-id":"<tenant-id>","x-ms-licensecategorization":"BASE","x-ms-licensecontext":"POWERAPPS","x-ms-user-agent":"PowerApps/<version> (Web Player; AppName=<app-id>)"}
POWERAPPS_HOLIDAY_DATES=2026-01-01,2026-01-06,2026-04-06,2026-05-01,2026-05-14,2026-05-25,2026-06-04,2026-08-15,2026-10-26,2026-11-01,2026-12-08,2026-12-25,2026-12-26
```

## Usage

### Create and submit

```bash
poetry run powerapps-time fill-month --submit
```

Flow:
1. ask SharePoint item id
2. fetch existing item metadata (year/month/email/etag)
3. build month entries and apply overrides
4. ask `If-Match` and PATCH `hoursjson`

### Other commands

```bash
poetry run powerapps-time preview
poetry run powerapps-time validate
poetry run powerapps-time submit --item-id <item-id> --yes
```

## Notes

- Empty/holiday/leave/weekend entries send `WorkedTime_Decimal`, `deltaAZ_Decimal`, `deltaAZ_OT_Decimal` as `null`.
- Refresh bearer token and session/request headers if auth/session becomes stale.

## Tests

```bash
poetry run pytest
```
