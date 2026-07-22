"""
agents/remediation_planner_agent.py
------------------------------------
Specialised agent #3 in the multi-agent pipeline: PLAN.

Given the alert, the diagnostics context, and the RootCauseAnalysisAgent's
hypothesis, this agent proposes a structured, safe, idempotent remediation
plan (list of RemediationAction). It never queries Azure directly and never
executes anything — that is ExecutionAgent's job.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from llm.foundry_client import FoundryClient
from models.alert import Alert
from models.rca_result import RCAResult
from models.remediation_plan import RemediationPlan

logger = logging.getLogger(__name__)


PLANNER_SYSTEM_PROMPT = """
You are a Remediation Planning agent for Azure cloud incidents.
You receive an alert, supporting diagnostic context, and a root-cause
hypothesis produced by another agent. Your job is to propose a safe,
idempotent remediation plan as structured JSON.

Always respond with a single valid JSON object matching this schema:
{
  "summary": "<one-paragraph incident summary>",
  "root_cause_hypothesis": "<restate or refine the given root cause>",
  "severity_assessment": "<Sev0|Sev1|Sev2|Sev3|Sev4>",
  "confidence_score": <0.0-1.0>,
  "requires_human_approval": <true|false>,
  "actions": [
    {
      "action_type": "<restart_resource|scale_out|scale_in|run_runbook|collect_diagnostics|notify|no_action>",
      "resource_id": "<ARM resource ID>",
      "runbook_name": "<name or empty>",
      "parameters": {},
      "rationale": "<why this action>",
      "safe_to_automate": <true|false>
    }
  ]
}

Rules:
- Only recommend actions you are confident are safe and idempotent.
- Set safe_to_automate=false for any destructive or irreversible action.
- Set requires_human_approval=true if ANY action is safe_to_automate=false.
- If the root-cause confidence is low or context is insufficient, recommend
  collect_diagnostics only.
"""


class RemediationPlannerAgent:
    """LLM-backed agent that turns an RCA hypothesis into an action plan."""

    def __init__(self, foundry: Optional[FoundryClient] = None) -> None:
        self._foundry = foundry or FoundryClient()

    def plan(self, alert: Alert, context_text: str, rca: RCAResult) -> RemediationPlan:
        logger.info("RemediationPlannerAgent — planning for alert %s", alert.alert_id)
        user_content = (
            f"{context_text}\n\n"
            f"## Root Cause Analysis (from RootCauseAnalysisAgent)\n"
            f"{rca.model_dump_json(indent=2)}"
        )
        raw_response = self._foundry.complete_json(PLANNER_SYSTEM_PROMPT, user_content)
        data = json.loads(raw_response)
        plan = RemediationPlan(**data)
        plan.raw_llm_response = raw_response
        logger.info(
            "Remediation plan received — %d actions, confidence %.0f%%",
            len(plan.actions),
            plan.confidence_score * 100,
        )
        return plan
