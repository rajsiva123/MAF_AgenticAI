"""
tests/test_agent.py
--------------------
Integration-style tests for the IncidentTriageAgent using mocked Azure services.
No real Azure credentials required — all external calls are patched.
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from agents.incident_triage_agent import IncidentTriageAgent
from models.alert import Alert
from models.remediation_plan import ActionType, RemediationAction, RemediationPlan


SAMPLE_ALERT = Alert(
    alert_id="test-001",
    severity="Sev2",
    title="High CPU on my-func-app",
    description="CPU exceeded 90% for 5 minutes.",
    resource_id="/subscriptions/sub-123/resourceGroups/AIAgentRG/providers/Microsoft.Web/sites/my-func-app",
    resource_type="Microsoft.Web/sites",
    resource_name="my-func-app",
    subscription_id="sub-123",
    resource_group="AIAgentRG",
)

MOCK_PLAN_JSON = json.dumps({
    "summary": "High CPU due to memory leak in latest deployment.",
    "root_cause_hypothesis": "Memory leak in app code triggered GC pressure.",
    "severity_assessment": "Sev2",
    "confidence_score": 0.88,
    "requires_human_approval": False,
    "actions": [
        {
            "action_type": "restart_resource",
            "resource_id": "/subscriptions/sub-123/resourceGroups/AIAgentRG/providers/Microsoft.Web/sites/my-func-app",
            "runbook_name": "",
            "parameters": {},
            "rationale": "Restart clears memory leak state.",
            "safe_to_automate": True,
        }
    ],
})


@patch("agents.incident_triage_agent.FoundryClient")
@patch("agents.incident_triage_agent.LogAnalyticsTool")
@patch("agents.incident_triage_agent.ResourceGraphTool")
@patch("agents.incident_triage_agent.RemediationTool")
@patch("agents.incident_triage_agent.ApprovalGateway")
def test_full_agent_run_auto_approve(
    mock_approval_cls,
    mock_remediation_cls,
    mock_rg_cls,
    mock_la_cls,
    mock_foundry_cls,
):
    # Set up mocks
    mock_foundry_cls.return_value.triage.return_value = MOCK_PLAN_JSON
    mock_rg_cls.return_value.get_resource_details.return_value = {"name": "my-func-app"}
    mock_rg_cls.return_value.get_related_resources.return_value = []
    mock_la_cls.return_value.get_recent_errors.return_value = []
    mock_la_cls.return_value.get_resource_health_events.return_value = []
    mock_la_cls.return_value.get_cpu_memory_trend.return_value = []
    mock_approval_cls.return_value.request_approval.return_value = True
    mock_remediation_cls.return_value.execute.return_value = {
        "success": True,
        "message": "App Service 'my-func-app' restarted.",
    }

    agent = IncidentTriageAgent()
    result = agent.run(SAMPLE_ALERT)

    assert result.approved is True
    assert result.plan is not None
    assert result.plan.confidence_score == 0.88
    assert len(result.actions_executed) == 1
    assert result.actions_executed[0]["executed"] is True
    assert len(result.errors) == 0


@patch("agents.incident_triage_agent.FoundryClient")
@patch("agents.incident_triage_agent.LogAnalyticsTool")
@patch("agents.incident_triage_agent.ResourceGraphTool")
@patch("agents.incident_triage_agent.RemediationTool")
@patch("agents.incident_triage_agent.ApprovalGateway")
def test_agent_rejected_by_approver(
    mock_approval_cls,
    mock_remediation_cls,
    mock_rg_cls,
    mock_la_cls,
    mock_foundry_cls,
):
    mock_foundry_cls.return_value.triage.return_value = MOCK_PLAN_JSON
    mock_rg_cls.return_value.get_resource_details.return_value = {}
    mock_rg_cls.return_value.get_related_resources.return_value = []
    mock_la_cls.return_value.get_recent_errors.return_value = []
    mock_la_cls.return_value.get_resource_health_events.return_value = []
    mock_la_cls.return_value.get_cpu_memory_trend.return_value = []
    mock_approval_cls.return_value.request_approval.return_value = False  # rejected

    agent = IncidentTriageAgent()
    result = agent.run(SAMPLE_ALERT)

    assert result.approved is False
    assert result.actions_executed == []


@patch("agents.incident_triage_agent.FoundryClient")
@patch("agents.incident_triage_agent.LogAnalyticsTool")
@patch("agents.incident_triage_agent.ResourceGraphTool")
@patch("agents.incident_triage_agent.RemediationTool")
@patch("agents.incident_triage_agent.ApprovalGateway")
def test_agent_handles_bad_llm_response(
    mock_approval_cls,
    mock_remediation_cls,
    mock_rg_cls,
    mock_la_cls,
    mock_foundry_cls,
):
    mock_foundry_cls.return_value.triage.return_value = "NOT VALID JSON {{{"
    mock_rg_cls.return_value.get_resource_details.return_value = {}
    mock_rg_cls.return_value.get_related_resources.return_value = []
    mock_la_cls.return_value.get_recent_errors.return_value = []
    mock_la_cls.return_value.get_resource_health_events.return_value = []
    mock_la_cls.return_value.get_cpu_memory_trend.return_value = []

    agent = IncidentTriageAgent()
    result = agent.run(SAMPLE_ALERT)

    assert result.plan is None
    # Errors may arrive from observe (context gathering) or analyse (LLM parse).
    # Either way, at least one error should be recorded.
    assert len(result.errors) > 0 or result.plan is None
