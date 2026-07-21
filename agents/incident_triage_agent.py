"""
agents/incident_triage_agent.py
--------------------------------
MAF Cloud Incident Triage Agent — core orchestration loop.

Loop:
  OBSERVE  → Collect alert + Log Analytics + Resource Graph context
  ANALYSE  → Call Foundry LLM with all context → receive structured plan
  PLAN     → Parse and validate RemediationPlan from LLM response
  APPROVE  → Human-in-the-loop approval gate (if required)
  ACT      → Execute only safe_to_automate actions automatically
  AUDIT    → Log outcome for observability

The agent is stateless per invocation. State persistence (conversation history,
vector memory) can be layered on top via a MAF session store.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from approval.human_approval import ApprovalGateway
from llm.foundry_client import FoundryClient
from models.alert import Alert
from models.remediation_plan import ActionType, RemediationAction, RemediationPlan
from tools.log_analytics_tool import LogAnalyticsTool
from tools.remediation_tool import RemediationTool
from tools.resource_graph_tool import ResourceGraphTool

logger = logging.getLogger(__name__)


@dataclass
class TriageResult:
    """Full audit record produced by one agent invocation."""

    alert: Alert
    plan: Optional[RemediationPlan] = None
    approved: bool = False
    actions_executed: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    completed_at: datetime = field(default_factory=datetime.utcnow)

    def summary(self) -> str:
        lines = [
            f"Alert       : {self.alert.title} ({self.alert.severity})",
            f"Approved    : {self.approved}",
            f"Actions run : {len(self.actions_executed)}",
        ]
        if self.plan:
            lines += [
                f"Confidence  : {self.plan.confidence_score:.0%}",
                f"Root cause  : {self.plan.root_cause_hypothesis}",
            ]
        if self.errors:
            lines.append(f"Errors      : {'; '.join(self.errors)}")
        return "\n".join(lines)


class IncidentTriageAgent:
    """
    MAF agent that triages Azure cloud incidents end-to-end.

    Usage:
        agent = IncidentTriageAgent()
        result = agent.run(alert)
        print(result.summary())
    """

    def __init__(self) -> None:
        self._foundry = FoundryClient()
        self._log_analytics = LogAnalyticsTool()
        self._resource_graph = ResourceGraphTool()
        self._remediation = RemediationTool()
        self._approval = ApprovalGateway()

    # ── Public API ────────────────────────────────────────────────────

    def run(self, alert: Alert) -> TriageResult:
        result = TriageResult(alert=alert)
        logger.info("=== IncidentTriageAgent.run — alert: %s ===", alert.alert_id)

        # ── OBSERVE ───────────────────────────────────────────────────
        context = self._observe(alert, result)

        # ── ANALYSE ───────────────────────────────────────────────────
        plan = self._analyse(context, result)
        if plan is None:
            return result
        result.plan = plan

        # ── APPROVE ───────────────────────────────────────────────────
        approved = self._approval.request_approval(plan, alert.title)
        result.approved = approved
        if not approved:
            logger.info("Plan rejected by approver — no actions will be executed.")
            return result

        # ── ACT ───────────────────────────────────────────────────────
        self._act(plan, result)

        # ── AUDIT ─────────────────────────────────────────────────────
        logger.info("Triage complete.\n%s", result.summary())
        return result

    # ── Private steps ─────────────────────────────────────────────────

    def _observe(self, alert: Alert, result: TriageResult) -> str:
        """Gather all context needed for the LLM analysis call."""
        logger.info("OBSERVE — gathering context for %s", alert.resource_id)
        sections: List[str] = []

        # 1. Alert details
        sections.append(f"## Alert\n{alert.model_dump_json(indent=2)}")

        # 2. Resource state from Resource Graph
        try:
            resource_details = self._resource_graph.get_resource_details(alert.resource_id)
            sections.append(f"## Resource State\n{json.dumps(resource_details, indent=2, default=str)}")

            related = self._resource_graph.get_related_resources(alert.resource_group)
            sections.append(f"## Related Resources ({len(related)} found)\n"
                            + json.dumps(related[:10], indent=2, default=str))
        except Exception as exc:
            msg = f"Resource Graph query failed: {exc}"
            logger.warning(msg)
            result.errors.append(msg)

        # 3. Recent errors from Log Analytics
        try:
            errors = self._log_analytics.get_recent_errors(alert.resource_name)
            sections.append(f"## Recent Log Errors ({len(errors)} entries)\n"
                            + json.dumps(errors[:10], indent=2, default=str))

            activity = self._log_analytics.get_resource_health_events(alert.resource_id)
            sections.append(f"## Activity Log Events ({len(activity)} entries)\n"
                            + json.dumps(activity[:10], indent=2, default=str))

            perf = self._log_analytics.get_cpu_memory_trend(alert.resource_name)
            sections.append(f"## CPU/Memory Trend\n{json.dumps(perf[:10], indent=2, default=str)}")
        except Exception as exc:
            msg = f"Log Analytics query failed: {exc}"
            logger.warning(msg)
            result.errors.append(msg)

        full_context = "\n\n".join(sections)
        logger.debug("Context gathered (%d chars)", len(full_context))
        return full_context

    def _analyse(self, context: str, result: TriageResult) -> Optional[RemediationPlan]:
        """Call Foundry LLM and parse the structured remediation plan."""
        logger.info("ANALYSE — calling Foundry LLM")
        try:
            raw_response = self._foundry.triage(context)
            plan_dict = json.loads(raw_response)
            plan = RemediationPlan(**plan_dict)
            plan.raw_llm_response = raw_response
            logger.info("LLM plan received — %d actions, confidence %.0f%%",
                        len(plan.actions), plan.confidence_score * 100)
            return plan
        except json.JSONDecodeError as exc:
            msg = f"LLM response was not valid JSON: {exc}"
            logger.error(msg)
            result.errors.append(msg)
            return None
        except Exception as exc:
            msg = f"Foundry LLM call failed: {exc}"
            logger.error(msg)
            result.errors.append(msg)
            return None

    def _act(self, plan: RemediationPlan, result: TriageResult) -> None:
        """Execute actions that are safe_to_automate. Log all outcomes."""
        logger.info("ACT — executing %d actions", len(plan.actions))
        for action in plan.actions:
            if action.action_type == ActionType.NO_ACTION:
                continue
            if not action.safe_to_automate:
                logger.info("Skipping action (not safe_to_automate): %s", action.action_type)
                result.actions_executed.append({
                    "action": action.action_type.value,
                    "executed": False,
                    "reason": "requires_manual_execution",
                })
                continue
            try:
                outcome = self._remediation.execute(action)
                result.actions_executed.append({
                    "action": action.action_type.value,
                    "resource": action.resource_id,
                    "executed": True,
                    **outcome,
                })
            except Exception as exc:
                msg = f"Action {action.action_type} failed: {exc}"
                logger.error(msg)
                result.errors.append(msg)
                result.actions_executed.append({
                    "action": action.action_type.value,
                    "executed": False,
                    "error": str(exc),
                })
