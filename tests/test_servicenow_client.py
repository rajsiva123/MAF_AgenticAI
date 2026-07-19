"""Tests for ServiceNow client behavior with mocked HTTP calls."""

from __future__ import annotations

import requests

from tools.servicenow_client import ServiceNowClient


class DummyResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self) -> dict:
        return self._payload


def test_create_incident_retries_then_succeeds(monkeypatch) -> None:
    client = ServiceNowClient("https://example.service-now.com", "user", "pass", max_retries=2)
    calls = {"count": 0}

    def fake_request(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise requests.ConnectionError("transient")
        return DummyResponse({"result": {"number": "INC0010001"}})

    monkeypatch.setattr(client._session, "request", fake_request)

    result = client.create_incident("Short", "Desc", "3")

    assert result["result"]["number"] == "INC0010001"
    assert calls["count"] == 2


def test_get_incident_raises_after_retries(monkeypatch) -> None:
    client = ServiceNowClient("https://example.service-now.com", "user", "pass", max_retries=2)

    def always_fail(*args, **kwargs):
        raise requests.ConnectionError("still down")

    monkeypatch.setattr(client._session, "request", always_fail)

    try:
        client.get_incident("INC0010001")
        assert False, "Expected RuntimeError"
    except RuntimeError as exc:
        assert "failed after 2 attempts" in str(exc)


def test_search_incidents_url_encodes_query(monkeypatch) -> None:
    client = ServiceNowClient("https://example.service-now.com", "user", "pass")
    captured: dict[str, str] = {}

    def fake_request(method, url, **kwargs):
        captured["url"] = url
        return DummyResponse({"result": []})

    monkeypatch.setattr(client._session, "request", fake_request)
    client.search_incidents("vpn & email")
    assert "short_descriptionLIKEvpn%20%26%20email" in captured["url"]
