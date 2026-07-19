"""Tests for triage classification behavior."""

from agents.triage_agent import TriageAgent


def test_triage_incident_high_priority() -> None:
    triage = TriageAgent().classify("Critical production down issue: login failed")
    assert triage.ticket_type == "incident"
    assert triage.priority == "1"
    assert triage.category == "identity_access"
    assert triage.sentiment == "neutral"
