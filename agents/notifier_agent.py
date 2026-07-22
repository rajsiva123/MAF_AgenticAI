"""
agents/notifier_agent.py
--------------------------
Specialised agent #6 in the multi-agent pipeline: AUDIT / NOTIFY.

Final step of the orchestration pipeline: logs the structured outcome for
observability, and optionally posts a summary card to Teams (if
TEAMS_WEBHOOK_URL is configured) independent of any per-action "notify"
actions the RemediationPlannerAgent may have proposed.
"""
from __future__ import annotations

import logging

import requests

from config.settings import settings
from models.triage_result import TriageResult

logger = logging.getLogger(__name__)


class NotifierAgent:
    """Logs the final triage outcome and optionally posts a Teams summary."""

    def notify(self, result: TriageResult) -> None:
        logger.info("Triage complete.\n%s", result.summary())

        webhook_url = settings.teams_webhook_url
        if not webhook_url:
            logger.debug("NotifierAgent — no TEAMS_WEBHOOK_URL configured, skipping card.")
            return

        card = {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "themeColor": "2DC72D" if result.approved else "FF6600",
            "summary": f"Triage complete: {result.alert.title}",
            "title": f"✅ Incident Triage Summary — {result.alert.title}",
            "text": result.summary().replace("\n", "\n\n"),
        }
        try:
            resp = requests.post(webhook_url, json=card, timeout=10)
            logger.info("NotifierAgent — Teams summary posted (HTTP %s)", resp.status_code)
        except Exception as exc:
            logger.error("NotifierAgent — Teams notification failed: %s", exc)
