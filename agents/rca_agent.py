"""
agents/rca_agent.py
--------------------
Specialised agent #2 in the multi-agent pipeline: ANALYSE (root cause only).

Calls the Foundry LLM with a system prompt focused *purely* on identifying
the most likely root cause of an incident — it does NOT propose remediation
actions. That responsibility belongs to RemediationPlannerAgent, which
consumes this agent's output as input. Splitting these two concerns lets
each prompt stay small and focused, and lets you swap/tune one without
affecting the other.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from llm.foundry_client import FoundryClient
from models.alert import Alert
from models.rca_result import RCAResult

logger = logging.getLogger(__name__)


RCA_SYSTEM_PROMPT = """
You are a Root Cause Analysis (RCA) agent for Azure cloud incidents.
Your ONLY job is to analyse the alert and supporting context (logs, resource
state, activity events) and identify the most likely root cause. You do NOT
propose remediation actions — another agent handles that.

Always respond with a single valid JSON object matching this schema:
{
  "summary": "<one-paragraph incident summary>",
  "root_cause_hypothesis": "<most likely root cause>",
  "severity_assessment": "<Sev0|Sev1|Sev2|Sev3|Sev4>",
  "confidence_score": <0.0-1.0>
}

Rules:
- Base your hypothesis strictly on the provided context; do not invent data.
- If context is insufficient to form a confident hypothesis, say so in the
  summary and set confidence_score low (< 0.4).
"""


class RootCauseAnalysisAgent:
    """LLM-backed agent that produces a root-cause hypothesis only."""

    def __init__(self, foundry: Optional[FoundryClient] = None) -> None:
        self._foundry = foundry or FoundryClient()

    def analyse(self, alert: Alert, context_text: str) -> RCAResult:
        logger.info("RootCauseAnalysisAgent — analysing alert %s", alert.alert_id)
        raw_response = self._foundry.complete_json(RCA_SYSTEM_PROMPT, context_text)
        data = json.loads(raw_response)
        result = RCAResult(**data)
        result.raw_llm_response = raw_response
        logger.info(
            "RCA complete — confidence %.0f%%, root cause: %s",
            result.confidence_score * 100,
            result.root_cause_hypothesis,
        )
        return result
