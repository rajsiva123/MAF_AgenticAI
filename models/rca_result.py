"""
models/rca_result.py
---------------------
Pydantic model for the output of the RootCauseAnalysisAgent — a focused
root-cause hypothesis, produced *before* any remediation actions are planned.

Keeping this separate from RemediationPlan lets the RCA agent and the
Remediation Planner agent be swapped, tested, or re-prompted independently.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class RCAResult(BaseModel):
    """Root-cause analysis produced by the RootCauseAnalysisAgent."""

    summary: str = Field(..., description="One-paragraph summary of the incident analysis")
    root_cause_hypothesis: str = Field(..., description="Most likely root cause")
    severity_assessment: str = Field(..., description="Assessed severity after context review")
    confidence_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="LLM confidence 0-1"
    )
    raw_llm_response: str = Field(default="", description="Original LLM output (for audit)")
