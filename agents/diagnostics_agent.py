"""
agents/diagnostics_agent.py
----------------------------
Specialised agent #1 in the multi-agent pipeline: OBSERVE.

Gathers all context needed by downstream agents (Resource Graph state,
related resources, Log Analytics errors/activity/perf trend) and returns
it as a single serialised context string plus any collection errors.

This agent performs no LLM calls — it is purely a data-gathering step,
kept separate so it can be tested, cached, or swapped independently of
the reasoning agents.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import List

from models.alert import Alert
from tools.log_analytics_tool import LogAnalyticsTool
from tools.resource_graph_tool import ResourceGraphTool

logger = logging.getLogger(__name__)


@dataclass
class DiagnosticsContext:
    """Result of the diagnostics-gathering step."""

    context_text: str
    errors: List[str] = field(default_factory=list)


class DiagnosticsAgent:
    """Gathers Resource Graph + Log Analytics context for an alert."""

    def __init__(self) -> None:
        self._resource_graph = ResourceGraphTool()
        self._log_analytics = LogAnalyticsTool()

    def gather(self, alert: Alert) -> DiagnosticsContext:
        logger.info("DiagnosticsAgent — gathering context for %s", alert.resource_id)
        sections: List[str] = [f"## Alert\n{alert.model_dump_json(indent=2)}"]
        errors: List[str] = []

        try:
            resource_details = self._resource_graph.get_resource_details(alert.resource_id)
            sections.append(f"## Resource State\n{json.dumps(resource_details, indent=2, default=str)}")

            related = self._resource_graph.get_related_resources(alert.resource_group)
            sections.append(
                f"## Related Resources ({len(related)} found)\n"
                + json.dumps(related[:10], indent=2, default=str)
            )
        except Exception as exc:
            msg = f"Resource Graph query failed: {exc}"
            logger.warning(msg)
            errors.append(msg)

        try:
            recent_errors = self._log_analytics.get_recent_errors(alert.resource_name)
            sections.append(
                f"## Recent Log Errors ({len(recent_errors)} entries)\n"
                + json.dumps(recent_errors[:10], indent=2, default=str)
            )

            activity = self._log_analytics.get_resource_health_events(alert.resource_id)
            sections.append(
                f"## Activity Log Events ({len(activity)} entries)\n"
                + json.dumps(activity[:10], indent=2, default=str)
            )

            perf = self._log_analytics.get_cpu_memory_trend(alert.resource_name)
            sections.append(f"## CPU/Memory Trend\n{json.dumps(perf[:10], indent=2, default=str)}")
        except Exception as exc:
            msg = f"Log Analytics query failed: {exc}"
            logger.warning(msg)
            errors.append(msg)

        context_text = "\n\n".join(sections)
        logger.debug("DiagnosticsAgent context gathered (%d chars)", len(context_text))
        return DiagnosticsContext(context_text=context_text, errors=errors)
