"""
tests/test_orchestrator.py
----------------------------
Tests for the multi-agent OrchestratorAgent pipeline (Diagnostics -> RCA ->
Planner -> Approval -> Execution -> Notifier), using mocked Azure/Foundry
calls. No real Azure credentials required.
"""
import json
from unittest.mock import MagicMock, patch

from agents.orchestrator_agent import OrchestratorAgent
from models.alert import Alert

SAMPLE_ALERT = Alert(
    alert_id="test-002",
    severity="Sev2",
    title="High CPU on my-func-app",
    description="CPU exceeded 90% for 5 minutes.",
    resource_id="/subscriptions/sub-123/resourceGroups/AIAgentRG/providers/Microsoft.Web/sites/my-func-app",
    resource_type="Microsoft.Web/sites",
    resource_name="my-func-app",
    subscription_id="sub-123",
    resource_group="AIAgentRG",
)

MOCK_RCA_JSON = json.dumps({
    "summary": "High CPU due to memory leak in latest deployment.",
    "root_cause_hypothesis": "Memory leak in app code triggered GC pressure.",
    "severity_assessment": "Sev2",
    "confidence_score": 0.9,
})

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


def _patch_common():
    """Return a stack of patches shared by every orchestrator test."""
    return [
        patch("agents.orchestrator_agent.FoundryClient"),
        patch("agents.diagnostics_agent.LogAnalyticsTool"),
        patch("agents.diagnostics_agent.ResourceGraphTool"),
        patch("agents.execution_agent.RemediationTool"),
        patch("agents.approval_agent.ApprovalGateway"),
    ]


@patch("agents.approval_agent.ApprovalGateway")
@patch("agents.execution_agent.RemediationTool")
@patch("agents.diagnostics_agent.ResourceGraphTool")
@patch("agents.diagnostics_agent.LogAnalyticsTool")
@patch("agents.orchestrator_agent.FoundryClient")
def test_orchestrator_full_run_auto_approve(
    mock_foundry_cls,
    mock_la_cls,
    mock_rg_cls,
    mock_remediation_cls,
    mock_approval_cls,
):
    # Foundry: first call -> RCA JSON, second call -> plan JSON
    mock_foundry_instance = mock_foundry_cls.return_value
    mock_foundry_instance.complete_json.side_effect = [MOCK_RCA_JSON, MOCK_PLAN_JSON]

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

    orchestrator = OrchestratorAgent()
    result = orchestrator.run(SAMPLE_ALERT)

    assert result.approved is True
    assert result.plan is not None
    assert result.plan.confidence_score == 0.88
    assert len(result.actions_executed) == 1
    assert result.actions_executed[0]["executed"] is True
    assert len(result.errors) == 0
    # Two Foundry calls: one for RCA, one for the remediation plan
    assert mock_foundry_instance.complete_json.call_count == 2


@patch("agents.approval_agent.ApprovalGateway")
@patch("agents.execution_agent.RemediationTool")
@patch("agents.diagnostics_agent.ResourceGraphTool")
@patch("agents.diagnostics_agent.LogAnalyticsTool")
@patch("agents.orchestrator_agent.FoundryClient")
def test_orchestrator_rejected_by_approver(
    mock_foundry_cls,
    mock_la_cls,
    mock_rg_cls,
    mock_remediation_cls,
    mock_approval_cls,
):
    mock_foundry_cls.return_value.complete_json.side_effect = [MOCK_RCA_JSON, MOCK_PLAN_JSON]
    mock_rg_cls.return_value.get_resource_details.return_value = {}
    mock_rg_cls.return_value.get_related_resources.return_value = []
    mock_la_cls.return_value.get_recent_errors.return_value = []
    mock_la_cls.return_value.get_resource_health_events.return_value = []
    mock_la_cls.return_value.get_cpu_memory_trend.return_value = []
    mock_approval_cls.return_value.request_approval.return_value = False

    orchestrator = OrchestratorAgent()
    result = orchestrator.run(SAMPLE_ALERT)

    assert result.approved is False
    assert result.actions_executed == []


@patch("agents.approval_agent.ApprovalGateway")
@patch("agents.execution_agent.RemediationTool")
@patch("agents.diagnostics_agent.ResourceGraphTool")
@patch("agents.diagnostics_agent.LogAnalyticsTool")
@patch("agents.orchestrator_agent.FoundryClient")
def test_orchestrator_handles_bad_rca_response(
    mock_foundry_cls,
    mock_la_cls,
    mock_rg_cls,
    mock_remediation_cls,
    mock_approval_cls,
):
    mock_foundry_cls.return_value.complete_json.return_value = "NOT VALID JSON {{{"
    mock_rg_cls.return_value.get_resource_details.return_value = {}
    mock_rg_cls.return_value.get_related_resources.return_value = []
    mock_la_cls.return_value.get_recent_errors.return_value = []
    mock_la_cls.return_value.get_resource_health_events.return_value = []
    mock_la_cls.return_value.get_cpu_memory_trend.return_value = []

    orchestrator = OrchestratorAgent()
    result = orchestrator.run(SAMPLE_ALERT)

    assert result.plan is None
    assert len(result.errors) > 0
