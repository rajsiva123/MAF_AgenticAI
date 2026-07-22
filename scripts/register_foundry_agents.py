"""
scripts/register_foundry_agents.py
------------------------------------
Registers the LLM-backed pipeline agents (RootCauseAnalysisAgent,
RemediationPlannerAgent) as persistent Azure AI Foundry Agents, so they are
visible and individually testable in the Foundry Agents Playground.

This is idempotent: if an agent with the same name already exists in the
project, its instructions/description are updated instead of creating a
duplicate.

NOTE: This only affects what's visible/testable in the Foundry portal. The
running Function App (agents/rca_agent.py, agents/remediation_planner_agent.py)
still calls raw chat completions via FoundryClient.complete_json() — it does
NOT invoke these Agent IDs at runtime. Keep the system prompts below in sync
with agents/rca_agent.py and agents/remediation_planner_agent.py.

Usage:
    source .venv/bin/activate
    python3 scripts/register_foundry_agents.py

Requires: `az login` (uses DefaultAzureCredential -> AzureCliCredential) and
AZURE_AI_PROJECT_ENDPOINT / AZURE_FOUNDRY_MODEL_NAME set in .env.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.rca_agent import RCA_SYSTEM_PROMPT
from agents.remediation_planner_agent import PLANNER_SYSTEM_PROMPT
from config.settings import settings

# Registry of agents to keep in sync with Foundry. Add new entries here as
# new LLM-backed pipeline agents are introduced.
AGENT_DEFINITIONS = [
    {
        "name": "RCA-Agent",
        "description": (
            "Root Cause Analysis agent - identifies most likely root cause "
            "from alert + diagnostic context (no remediation actions)."
        ),
        "instructions": RCA_SYSTEM_PROMPT.strip(),
    },
    {
        "name": "Remediation-Planner-Agent",
        "description": (
            "Remediation Planner agent - turns an RCA hypothesis into a "
            "structured, safe, idempotent remediation plan."
        ),
        "instructions": PLANNER_SYSTEM_PROMPT.strip(),
    },
]

OUTPUT_FILE = Path(__file__).resolve().parent / "foundry_agents.json"


def main() -> None:
    from azure.ai.agents import AgentsClient  # lazy import
    from azure.identity import DefaultAzureCredential  # lazy import

    credential = DefaultAzureCredential()
    agents_client = AgentsClient(endpoint=settings.ai_project_endpoint, credential=credential)

    existing = {a.name: a for a in agents_client.list_agents()}
    registered: dict[str, str] = {}

    for definition in AGENT_DEFINITIONS:
        name = definition["name"]
        if name in existing:
            agent = agents_client.update_agent(
                existing[name].id,
                model=settings.foundry_model_name,
                description=definition["description"],
                instructions=definition["instructions"],
            )
            print(f"Updated existing agent: {name} ({agent.id})")
        else:
            agent = agents_client.create_agent(
                model=settings.foundry_model_name,
                name=name,
                description=definition["description"],
                instructions=definition["instructions"],
            )
            print(f"Created new agent: {name} ({agent.id})")
        registered[name] = agent.id

    OUTPUT_FILE.write_text(json.dumps(registered, indent=2) + "\n")
    print(f"\nAgent IDs written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
