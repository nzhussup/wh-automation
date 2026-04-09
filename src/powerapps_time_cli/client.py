from __future__ import annotations

from typing import Any

import httpx

from powerapps_time_cli.calculations import ValidationError
from powerapps_time_cli.models import AppConfig, MonthlyPlan
from powerapps_time_cli.payload import build_payload


class PowerAppsClient:
    def __init__(self, config: AppConfig, timeout_seconds: float = 30.0) -> None:
        self._config = config
        self._timeout = timeout_seconds

    def _headers(
        self,
        *,
        request_method: str,
        request_url: str,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, str]:
        if not self._config.bearer_token:
            raise ValidationError(
                "Missing bearer token. Set POWERAPPS_BEARER_TOKEN in environment/.env."
            )

        headers = {
            "Authorization": f"Bearer {self._config.bearer_token}",
            "Content-Type": "application/json",
            "x-ms-request-method": request_method,
            "x-ms-request-url": request_url,
            "origin": self._config.origin,
            "referer": self._config.referer,
        }
        headers.update(self._config.extra_headers)
        if extra_headers:
            headers.update(extra_headers)
        return headers

    def fetch_item(self, request_url: str) -> dict[str, Any]:
        return self._invoke(request_method="GET", request_url=request_url, payload={})

    def submit_patch(self, plan: MonthlyPlan, request_url: str, if_match: str) -> dict[str, Any]:
        result = self._invoke(
            request_method="PATCH",
            request_url=request_url,
            payload=build_payload(plan),
            extra_headers={"if-match": if_match},
        )
        if "hoursjson" not in result:
            raise RuntimeError(
                "SharePoint PATCH response does not contain 'hoursjson'. "
                f"Response: {result}"
            )
        return result

    def _invoke(
        self,
        *,
        request_method: str,
        request_url: str,
        payload: dict[str, Any],
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(
                    self._config.invoke_url,
                    headers=self._headers(
                        request_method=request_method,
                        request_url=request_url,
                        extra_headers=extra_headers,
                    ),
                    json=payload,
                )
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Network failure: {exc}") from exc

        if response.status_code >= 400:
            body = response.text[:1000]
            raise RuntimeError(
                f"Request failed with HTTP {response.status_code}. "
                f"Response body (truncated): {body}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError(
                f"Server returned non-JSON response: {response.text[:1000]}"
            ) from exc

        if "error" in data:
            raise RuntimeError(f"Backend error response: {data}")
        return data
