"""
llm/foundry_client.py
---------------------
Azure AI Foundry LLM adapter for the MAF agent.

Uses `azure-ai-projects` SDK which targets an AI Foundry project endpoint.
The client is reusable across all agents in the system.

Auth: DefaultAzureCredential (Managed Identity in prod, az login in dev).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import settings

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """
You are an Azure Cloud Incident Triage AI Agent.
Your role is to:
1. Analyse the incoming Azure alert and any supporting context (logs, resource state).
2. Identify the most likely root cause.
3. Propose a safe, idempotent remediation plan as structured JSON.

Always respond with a single valid JSON object matching this schema:
{
  "summary": "<one-paragraph incident summary>",
  "root_cause_hypothesis": "<most likely root cause>",
  "severity_assessment": "<Sev0|Sev1|Sev2|Sev3|Sev4>",
  "confidence_score": <0.0–1.0>,
  "requires_human_approval": <true|false>,
  "actions": [
    {
      "action_type": "<restart_resource|scale_out|scale_in|run_runbook|collect_diagnostics|notify|no_action>",
      "resource_id": "<ARM resource ID>",
      "runbook_name": "<name or empty>",
      "parameters": {},
      "rationale": "<why this action>",
      "safe_to_automate": <true|false>
    }
  ]
}

Rules:
- Only recommend actions you are confident are safe and idempotent.
- Set safe_to_automate=false for any destructive or irreversible action.
- Set requires_human_approval=true if ANY action is safe_to_automate=false.
- If insufficient context, recommend collect_diagnostics only.
"""


class FoundryClient:
    """Thin wrapper around Azure AI Foundry for chat completions."""

    def __init__(self) -> None:
        from azure.ai.projects import AIProjectClient  # lazy import
        from azure.identity import DefaultAzureCredential  # lazy import
        credential = DefaultAzureCredential()
        self._client = AIProjectClient(
            endpoint=settings.ai_project_endpoint,
            credential=credential,
        )
        # azure-ai-projects >= 2.x exposes an OpenAI-compatible client via
        # get_openai_client(); this is the supported path for chat completions.
        self._openai_client = self._client.get_openai_client()
        self._model = settings.foundry_model_name
        logger.info("FoundryClient initialised — model: %s", self._model)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def triage(self, alert_context: str) -> str:
        """
        Send the alert context to Foundry and return the raw JSON string.

        Parameters
        ----------
        alert_context : str
            Serialised alert + log context built by the orchestration layer.

        Returns
        -------
        str
            Raw LLM response (expected to be a valid JSON string).
        """
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": alert_context},
        ]

        logger.debug("Sending triage request to Foundry (%d chars)", len(alert_context))

        # OpenAI-compatible chat completions call via the AI Foundry project client
        result = self._openai_client.chat.completions.create(
            model=self._model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.1,  # low temperature for deterministic plans
            max_completion_tokens=2048,
        )

        raw = result.choices[0].message.content
        logger.debug("Foundry response received (%d chars)", len(raw))
        return raw

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
