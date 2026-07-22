"""
agents/execution_agent.py
----------------------------
Specialised agent #5 in the multi-agent pipeline: ACT.

Executes only the safe_to_automate actions in an approved RemediationPlan,
via tools.remediation_tool.RemediationTool. Returns a list of per-action
outcome dicts plus any execution errors, mirroring the behaviour of the
legacy IncidentTriageAgent._act() step.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from models.remediation_plan import ActionType, RemediationPlan
from tools.remediation_tool import RemediationTool

logger = logging.getLogger(__name__)


class ExecutionAgent:
    """Executes approved, safe-to-automate remediation actions."""

    def __init__(self, remediation: Optional[RemediationTool] = None) -> None:
        self._remediation = remediation or RemediationTool()

    def execute(self, plan: RemediationPlan) -> Tuple[List[Dict[str, Any]], List[str]]:
        logger.info("ExecutionAgent — executing %d actions", len(plan.actions))
        actions_executed: List[Dict[str, Any]] = []
        errors: List[str] = []

        for action in plan.actions:
            if action.action_type == ActionType.NO_ACTION:
                continue
            if not action.safe_to_automate:
                logger.info("Skipping action (not safe_to_automate): %s", action.action_type)
                actions_executed.append({
                    "action": action.action_type.value,
                    "executed": False,
                    "reason": "requires_manual_execution",
                })
                continue
            try:
                outcome = self._remediation.execute(action)
                actions_executed.append({
                    "action": action.action_type.value,
                    "resource": action.resource_id,
                    "executed": True,
                    **outcome,
                })
            except Exception as exc:
                msg = f"Action {action.action_type} failed: {exc}"
                logger.error(msg)
                errors.append(msg)
                actions_executed.append({
                    "action": action.action_type.value,
                    "executed": False,
                    "error": str(exc),
                })

        return actions_executed, errors
