"""
tests/test_models.py
--------------------
Unit tests for Alert and RemediationPlan models.
No Azure credentials required.
"""
import pytest
from datetime import datetime
from models.alert import Alert
from models.remediation_plan import (
    ActionType,
    RemediationAction,
    RemediationPlan,
)


SAMPLE_PAYLOAD = {
    "id": "test-001",
    "data": {
        "essentials": {
            "alertId": "test-alert-001",
            "severity": "Sev1",
            "alertRule": "High CPU",
            "description": "CPU > 90%",
            "alertTargetIDs": [
                "/subscriptions/sub-123/resourceGroups/rg-test"
                "/providers/Microsoft.Web/sites/my-func-app"
            ],
        }
    },
}


def test_alert_from_azure_payload():
    alert = Alert.from_azure_payload(SAMPLE_PAYLOAD)
    assert alert.alert_id == "test-alert-001"
    assert alert.severity == "Sev1"
    assert alert.title == "High CPU"
    assert "sub-123" in alert.resource_id.lower()
    assert alert.resource_group == "rg-test"
    assert isinstance(alert.fired_at, datetime)


def test_alert_model_direct():
    alert = Alert(
        alert_id="a-001",
        severity="Sev2",
        title="Disk full",
        resource_id="/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm1",
    )
    assert alert.alert_id == "a-001"


def test_remediation_plan_valid():
    plan = RemediationPlan(
        summary="High CPU detected on func app.",
        root_cause_hypothesis="Memory leak in latest deployment.",
        severity_assessment="Sev1",
        confidence_score=0.85,
        requires_human_approval=True,
        actions=[
            RemediationAction(
                action_type=ActionType.RESTART_RESOURCE,
                resource_id="/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Web/sites/app",
                rationale="Restart clears in-memory state.",
                safe_to_automate=True,
            )
        ],
    )
    assert len(plan.actions) == 1
    assert plan.actions[0].action_type == ActionType.RESTART_RESOURCE
    assert plan.confidence_score == 0.85


def test_remediation_plan_confidence_bounds():
    with pytest.raises(Exception):
        RemediationPlan(
            summary="x",
            root_cause_hypothesis="x",
            severity_assessment="Sev0",
            confidence_score=1.5,  # invalid — must be ≤ 1.0
        )


def test_no_action_plan():
    plan = RemediationPlan(
        summary="No issues detected.",
        root_cause_hypothesis="False positive.",
        severity_assessment="Sev4",
        confidence_score=0.95,
        requires_human_approval=False,
        actions=[
            RemediationAction(
                action_type=ActionType.NO_ACTION,
                rationale="Alert resolved itself.",
                safe_to_automate=True,
            )
        ],
    )
    assert plan.actions[0].action_type == ActionType.NO_ACTION
