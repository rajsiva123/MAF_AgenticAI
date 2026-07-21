"""
models/alert.py
---------------
Pydantic model representing an incoming Azure Monitor alert payload.
MAF agents receive an Alert as the initial trigger.
"""
from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class Alert(BaseModel):
    """Normalised Azure Monitor / Activity Log alert."""

    alert_id: str = Field(..., description="Unique alert identifier (GUID or rule name)")
    severity: str = Field(..., description="Sev0–Sev4 or Critical/High/Medium/Low")
    title: str = Field(..., description="Short description of the alert")
    description: str = Field(default="", description="Detailed alert body")
    resource_id: str = Field(..., description="Full ARM resource ID of the affected resource")
    resource_type: str = Field(default="", description="e.g. Microsoft.Compute/virtualMachines")
    resource_name: str = Field(default="", description="Friendly resource name")
    subscription_id: str = Field(default="", description="Subscription containing the resource")
    resource_group: str = Field(default="", description="Resource group containing the resource")
    fired_at: datetime = Field(default_factory=datetime.utcnow)
    raw_payload: Dict[str, Any] = Field(default_factory=dict, description="Original alert payload")

    @classmethod
    def from_azure_payload(cls, payload: Dict[str, Any]) -> "Alert":
        """Parse an Azure Monitor common alert schema payload."""
        data = payload.get("data", {})
        essentials = data.get("essentials", {})
        resource_id = essentials.get("alertTargetIDs", [""])[0]
        parts = resource_id.lower().split("/")

        def _get(parts, key):
            try:
                idx = parts.index(key)
                return parts[idx + 1]
            except (ValueError, IndexError):
                return ""

        return cls(
            alert_id=essentials.get("alertId", payload.get("id", "unknown")),
            severity=essentials.get("severity", "unknown"),
            title=essentials.get("alertRule", "Unknown alert"),
            description=essentials.get("description", ""),
            resource_id=resource_id,
            resource_type=_get(parts, "providers"),
            resource_name=_get(parts, "virtualmachines") or parts[-1] if parts else "",
            subscription_id=_get(parts, "subscriptions"),
            resource_group=_get(parts, "resourcegroups"),
            fired_at=datetime.utcnow(),
            raw_payload=payload,
        )
