"""Escalation agent for ServiceNow incident creation and status lookup."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tools.servicenow_client import ServiceNowClient


@dataclass
class EscalationResult:
    """Result of escalation operations against ServiceNow."""

    action: str
    details: dict[str, Any]


class EscalationAgent:
    """Creates and queries incidents in ServiceNow."""

    def __init__(self, servicenow_client: ServiceNowClient) -> None:
        self._servicenow_client = servicenow_client

    def escalate(self, short_description: str, description: str, priority: str) -> EscalationResult:
        """Create an incident for unresolved issues."""

        created = self._servicenow_client.create_incident(short_description, description, priority)
        return EscalationResult(action="create_incident", details=created)

    def check_status(self, incident_number: str) -> EscalationResult:
        """Get incident status by number."""

        status = self._servicenow_client.get_incident(incident_number)
        return EscalationResult(action="check_status", details=status)
