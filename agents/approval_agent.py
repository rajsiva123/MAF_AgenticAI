"""
agents/approval_agent.py
--------------------------
Specialised agent #4 in the multi-agent pipeline: APPROVE.

Thin agent-shaped wrapper around approval.human_approval.ApprovalGateway,
kept as its own module so the orchestrator treats every pipeline step
uniformly as an "agent" and this step can be swapped (e.g. for a Teams
adaptive-card flow or a Logic App durable approval) without touching the
orchestrator.
"""
from __future__ import annotations

import logging
from typing import Optional

from approval.human_approval import ApprovalGateway
from models.remediation_plan import RemediationPlan

logger = logging.getLogger(__name__)


class ApprovalAgent:
    """Human-in-the-loop approval gate agent."""

    def __init__(self, gateway: Optional[ApprovalGateway] = None) -> None:
        self._gateway = gateway or ApprovalGateway()

    def review(self, plan: RemediationPlan, alert_title: str) -> bool:
        logger.info("ApprovalAgent — reviewing plan for '%s'", alert_title)
        return self._gateway.request_approval(plan, alert_title)
