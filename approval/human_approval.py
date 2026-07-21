"""
approval/human_approval.py
---------------------------
Human-in-the-loop approval gate for the MAF incident triage agent.

Modes (set via APPROVAL_MODE env var):
  - "auto"   — All plans are auto-approved (dev/test only).
  - "manual" — Prints plan to console and waits for user input (local dev).
  - "teams"  — Posts an adaptive card to Teams webhook and waits for acknowledgement.

In a production deployment this module would integrate with a durable approval
workflow (e.g., Azure Durable Functions, Logic Apps, or an ITSM system).
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from config.settings import settings
from models.remediation_plan import RemediationPlan

logger = logging.getLogger(__name__)


class ApprovalGateway:
    """Request and await human approval before executing a remediation plan."""

    def __init__(self) -> None:
        self._mode = settings.approval_mode.lower()

    def request_approval(self, plan: RemediationPlan, alert_title: str) -> bool:
        """
        Present the plan to a human reviewer.

        Returns True if approved, False if rejected.
        """
        if not plan.requires_human_approval:
            logger.info("Plan marked requires_human_approval=False — skipping gate.")
            return True

        if self._mode == "auto":
            logger.info("APPROVAL_MODE=auto — plan auto-approved (dev/test only).")
            return True
        elif self._mode == "teams":
            return self._teams_approval(plan, alert_title)
        else:
            return self._manual_approval(plan, alert_title)

    def _manual_approval(self, plan: RemediationPlan, alert_title: str) -> bool:
        """Interactive console approval for local development."""
        divider = "─" * 60
        print(f"\n{divider}")
        print("🔎 INCIDENT TRIAGE — HUMAN APPROVAL REQUIRED")
        print(divider)
        print(f"Alert         : {alert_title}")
        print(f"Summary       : {plan.summary}")
        print(f"Root cause    : {plan.root_cause_hypothesis}")
        print(f"Severity      : {plan.severity_assessment}")
        print(f"Confidence    : {plan.confidence_score:.0%}")
        print(f"\nProposed actions ({len(plan.actions)}):")
        for i, action in enumerate(plan.actions, start=1):
            auto = "✅ auto" if action.safe_to_automate else "🔒 manual"
            print(f"  {i}. [{auto}] {action.action_type.value}")
            print(f"       Resource : {action.resource_id or '(n/a)'}")
            print(f"       Rationale: {action.rationale}")
        print(divider)

        choice = input("Approve plan? [y/n]: ").strip().lower()
        approved = choice in ("y", "yes")
        logger.info("Manual approval decision: %s", "APPROVED" if approved else "REJECTED")
        return approved

    def _teams_approval(self, plan: RemediationPlan, alert_title: str) -> bool:
        """
        Post an adaptive card to Teams and prompt for console confirmation.
        (Production: replace console prompt with a Logic App approval flow.)
        """
        webhook_url = settings.teams_webhook_url
        if not webhook_url:
            logger.warning("TEAMS_WEBHOOK_URL not set — falling back to manual approval.")
            return self._manual_approval(plan, alert_title)

        actions_text = "\n".join(
            f"- {a.action_type.value}: {a.rationale}" for a in plan.actions
        )
        card = {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "themeColor": "FF6600",
            "summary": f"Approval required: {alert_title}",
            "title": f"🚨 Incident Triage Approval — {alert_title}",
            "text": (
                f"**Summary:** {plan.summary}\n\n"
                f"**Root cause:** {plan.root_cause_hypothesis}\n\n"
                f"**Proposed actions:**\n{actions_text}\n\n"
                "_Reply to this thread or run the approval command to approve/reject._"
            ),
        }
        try:
            import requests  # lazy import
            resp = requests.post(webhook_url, json=card, timeout=10)
            logger.info("Teams notification sent (HTTP %s)", resp.status_code)
        except Exception as exc:
            logger.error("Teams notification failed: %s", exc)

        # In a real deployment: poll a queue / durable entity for the decision.
        # For PoC: fall back to console prompt.
        return self._manual_approval(plan, alert_title)
