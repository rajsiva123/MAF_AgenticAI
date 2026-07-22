"""
agents/orchestrator_agent.py
------------------------------
Multi-agent orchestrator for cloud incident triage.

Coordinates six specialised agents in a sequential pipeline:

  1. DiagnosticsAgent          — OBSERVE (Resource Graph + Log Analytics)
  2. RootCauseAnalysisAgent    — ANALYSE  (LLM: root cause only)
  3. RemediationPlannerAgent   — PLAN     (LLM: structured action plan)
  4. ApprovalAgent             — APPROVE  (human-in-the-loop gate)
  5. ExecutionAgent            — ACT      (execute safe_to_automate actions)
  6. NotifierAgent             — AUDIT    (log + optional Teams summary)

This is functionally equivalent to the legacy monolithic
IncidentTriageAgent, but each responsibility is its own agent/module —
independently testable, swappable, and (if desired) independently
deployable as its own Function/service. Both agents produce the same
TriageResult so callers (main.py, function_app.py) can use either.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from agents.approval_agent import ApprovalAgent
from agents.diagnostics_agent import DiagnosticsAgent
from agents.execution_agent import ExecutionAgent
from agents.notifier_agent import NotifierAgent
from agents.rca_agent import RootCauseAnalysisAgent
from agents.remediation_planner_agent import RemediationPlannerAgent
from llm.foundry_client import FoundryClient
from models.alert import Alert
from models.triage_result import TriageResult

logger = logging.getLogger(__name__)


class OrchestratorAgent:
    """
    Coordinates the multi-agent incident-triage pipeline.

    Usage:
        orchestrator = OrchestratorAgent()
        result = orchestrator.run(alert)
        print(result.summary())
    """

    def __init__(self) -> None:
        foundry = FoundryClient()
        self._diagnostics = DiagnosticsAgent()
        self._rca = RootCauseAnalysisAgent(foundry)
        self._planner = RemediationPlannerAgent(foundry)
        self._approval = ApprovalAgent()
        self._execution = ExecutionAgent()
        self._notifier = NotifierAgent()

    def run(self, alert: Alert) -> TriageResult:
        result = TriageResult(alert=alert)
        logger.info("=== OrchestratorAgent.run — alert: %s ===", alert.alert_id)

        # ── 1. DiagnosticsAgent (OBSERVE) ────────────────────────────
        diagnostics = self._diagnostics.gather(alert)
        result.errors.extend(diagnostics.errors)

        # ── 2. RootCauseAnalysisAgent (ANALYSE) ──────────────────────
        try:
            rca = self._rca.analyse(alert, diagnostics.context_text)
        except json.JSONDecodeError as exc:
            msg = f"RCA agent returned invalid JSON: {exc}"
            logger.error(msg)
            result.errors.append(msg)
            return result
        except Exception as exc:
            msg = f"RootCauseAnalysisAgent failed: {exc}"
            logger.error(msg)
            result.errors.append(msg)
            return result

        # ── 3. RemediationPlannerAgent (PLAN) ────────────────────────
        try:
            plan = self._planner.plan(alert, diagnostics.context_text, rca)
        except json.JSONDecodeError as exc:
            msg = f"Remediation planner returned invalid JSON: {exc}"
            logger.error(msg)
            result.errors.append(msg)
            return result
        except Exception as exc:
            msg = f"RemediationPlannerAgent failed: {exc}"
            logger.error(msg)
            result.errors.append(msg)
            return result
        result.plan = plan

        # ── 4. ApprovalAgent (APPROVE) ────────────────────────────────
        approved = self._approval.review(plan, alert.title)
        result.approved = approved
        if not approved:
            logger.info("Plan rejected by approver — no actions will be executed.")
            self._notifier.notify(result)
            return result

        # ── 5. ExecutionAgent (ACT) ───────────────────────────────────
        actions_executed, exec_errors = self._execution.execute(plan)
        result.actions_executed = actions_executed
        result.errors.extend(exec_errors)

        # ── 6. NotifierAgent (AUDIT) ──────────────────────────────────
        self._notifier.notify(result)
        return result
