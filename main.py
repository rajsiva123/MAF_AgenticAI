"""Entry point for a demo MAF-style service desk orchestration flow."""

from __future__ import annotations

import json

from azure.identity import DefaultAzureCredential

from agents.escalation_agent import EscalationAgent
from agents.resolver_agent import ResolverAgent
from agents.triage_agent import TriageAgent
from config.settings import load_settings
from tools.kb_search import KBSearch
from tools.powershell_tools import PowerShellToolRunner
from tools.servicenow_client import ServiceNowClient

MAX_SHORT_DESCRIPTION_LENGTH = 120


def run_conversation(user_message: str) -> dict[str, object]:
    """Run triage -> resolve -> escalate handoff chain."""

    settings = load_settings()

    # Demonstrates AAD-based auth path for Azure AI Foundry connection.
    # Token acquisition is intentionally lazy and only attempted when values are configured.
    credential = None
    if settings.foundry_project_endpoint:
        credential = DefaultAzureCredential(exclude_interactive_browser_credential=False)

    triage_agent = TriageAgent()
    triage = triage_agent.classify(user_message)

    resolver_agent = ResolverAgent(
        kb_search=KBSearch("kb"),
        powershell_runner=PowerShellToolRunner("scripts/powershell"),
    )
    resolver = resolver_agent.resolve(user_message)

    response: dict[str, object] = {
        "foundry": {
            "project_endpoint_configured": bool(settings.foundry_project_endpoint),
            "credential_created": credential is not None,
        },
        "triage": triage.__dict__,
        "resolver": resolver.__dict__,
    }

    if not resolver.resolved:
        servicenow = ServiceNowClient(
            settings.servicenow_instance_url,
            settings.servicenow_username,
            settings.servicenow_password,
            timeout_seconds=settings.servicenow_timeout_seconds,
            max_retries=settings.servicenow_max_retries,
        )
        escalation_agent = EscalationAgent(servicenow)
        escalation = escalation_agent.escalate(
            short_description=user_message[:MAX_SHORT_DESCRIPTION_LENGTH],
            description=user_message,
            priority=triage.priority,
        )
        response["escalation"] = escalation.__dict__

    return response


if __name__ == "__main__":
    sample_message = "My email service is down and restart did not help"
    print(json.dumps(run_conversation(sample_message), indent=2))
