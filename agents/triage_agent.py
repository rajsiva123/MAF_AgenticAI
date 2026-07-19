"""Ticket triage agent for coarse classification and prioritization."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TriageResult:
    """Structured triage output for downstream orchestration."""

    ticket_type: str
    category: str
    priority: str
    sentiment: str


class TriageAgent:
    """Classifies incoming user requests for service desk routing."""

    def classify(self, message: str) -> TriageResult:
        """Classify a ticket message into type/category/priority/sentiment."""

        text = message.lower()
        if any(word in text for word in ["error", "down", "cannot", "can't", "failed", "issue"]):
            ticket_type = "incident"
        elif any(word in text for word in ["how to", "help", "question", "what is"]):
            ticket_type = "question"
        else:
            ticket_type = "request"

        if any(word in text for word in ["password", "login", "account"]):
            category = "identity_access"
        elif any(word in text for word in ["service", "restart", "server", "application"]):
            category = "infrastructure"
        else:
            category = "general"

        if any(word in text for word in ["urgent", "critical", "production down"]):
            priority = "1"
        elif any(word in text for word in ["important", "soon", "degraded", "slow"]):
            priority = "2"
        else:
            priority = "3"
        sentiment = "negative" if any(word in text for word in ["angry", "frustrated", "upset", "not working"]) else "neutral"

        return TriageResult(ticket_type=ticket_type, category=category, priority=priority, sentiment=sentiment)
