"""
models/remediation_plan.py
--------------------------
Pydantic model for the structured remediation plan returned by the LLM.
The agent parses LLM JSON output into this model before acting.
"""
from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ActionType(str, Enum):
    RESTART_RESOURCE = "restart_resource"
    SCALE_OUT = "scale_out"
    SCALE_IN = "scale_in"
    RUN_RUNBOOK = "run_runbook"
    COLLECT_DIAGNOSTICS = "collect_diagnostics"
    NOTIFY = "notify"
    NO_ACTION = "no_action"


class RemediationAction(BaseModel):
    action_type: ActionType
    resource_id: str = Field(default="", description="ARM resource ID to act on")
    runbook_name: str = Field(default="", description="Automation Runbook name if applicable")
    parameters: Dict[str, Any] = Field(default_factory=dict)
    rationale: str = Field(default="", description="Why this action was chosen")
    safe_to_automate: bool = Field(
        default=False,
        description="True if this action can be executed without human approval",
    )


class RemediationPlan(BaseModel):
    """Full remediation plan produced by the LLM triage agent."""

    summary: str = Field(..., description="One-paragraph summary of the incident analysis")
    root_cause_hypothesis: str = Field(..., description="Most likely root cause")
    severity_assessment: str = Field(..., description="Assessed severity after context review")
    actions: List[RemediationAction] = Field(default_factory=list)
    requires_human_approval: bool = Field(
        default=True,
        description="Whether any action in this plan requires human sign-off",
    )
    confidence_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="LLM confidence 0–1"
    )
    raw_llm_response: str = Field(default="", description="Original LLM output (for audit)")
