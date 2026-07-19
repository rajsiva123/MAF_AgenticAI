"""ServiceNow REST Table API client with lightweight retry support."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any
from urllib.parse import quote

import requests


@dataclass
class ServiceNowClient:
    """Client for interacting with ServiceNow incident records."""

    instance_url: str
    username: str
    password: str
    timeout_seconds: int = 15
    max_retries: int = 3

    def __post_init__(self) -> None:
        self._session = requests.Session()
        self._session.auth = (self.username, self.password)
        self._session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})

    def create_incident(self, short_description: str, description: str, priority: str) -> dict[str, Any]:
        """Create a new ServiceNow incident."""

        payload = {
            "short_description": short_description,
            "description": description,
            "priority": priority,
        }
        return self._request("POST", "/api/now/table/incident", json=payload)

    def update_incident(self, sys_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        """Update an existing ServiceNow incident by sys_id."""

        return self._request("PATCH", f"/api/now/table/incident/{sys_id}", json=fields)

    def get_incident(self, number: str) -> dict[str, Any]:
        """Fetch an incident by incident number (example: INC0010001)."""

        encoded_number = quote(number, safe="")
        return self._request("GET", f"/api/now/table/incident?sysparm_query=number={encoded_number}")

    def search_incidents(self, short_description: str) -> dict[str, Any]:
        """Search incidents by short description text."""

        query = quote(short_description, safe="")
        return self._request(
            "GET",
            f"/api/now/table/incident?sysparm_query=short_descriptionLIKE{query}",
        )

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        """Perform a retried HTTP request and return parsed JSON response."""

        if not self.instance_url:
            raise ValueError("ServiceNow instance URL is required")

        url = f"{self.instance_url.rstrip('/')}{path}"
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self._session.request(method, url, timeout=self.timeout_seconds, **kwargs)
                response.raise_for_status()
                return response.json()
            except requests.RequestException as exc:
                last_error = exc
                if attempt == self.max_retries:
                    break
                time.sleep(0.2 * attempt)

        raise RuntimeError(f"ServiceNow request failed after {self.max_retries} attempts: {last_error}")
