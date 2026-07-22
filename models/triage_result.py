"""
models/triage_result.py
------------------------
Shared audit-record dataclass produced by both the monolithic
IncidentTriageAgent and the multi-agent OrchestratorAgent.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from models.alert import Alert
from models.remediation_plan import RemediationPlan


@dataclass
class TriageResult:
    """Full audit record produced by one agent (or agent pipeline) invocation."""

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
