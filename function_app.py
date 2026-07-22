"""
function_app.py
-----------------
Azure Functions (Python v2 programming model) entry point for the MAF
Cloud Incident Triage agent.

Exposes:
  POST /api/triage       - runs the legacy monolithic IncidentTriageAgent.
  POST /api/orchestrate  - runs the multi-agent OrchestratorAgent pipeline
                           (Diagnostics -> RCA -> Planner -> Approval ->
                           Execution -> Notifier).
  GET  /api/health       - simple liveness check.

Both triage routes accept an Azure Monitor common-alert-schema JSON body,
or a simplified {"demo": true} body to use the built-in demo alert.

This module reuses the existing project code (agents/, models/, llm/, tools/,
approval/, config/) which is packaged alongside this function app at deploy
time (see README / deploy instructions).
"""
from __future__ import annotations

import json
import logging

import azure.functions as func

from main import DEMO_ALERT_PAYLOAD, run_orchestrated, run_triage
from models.alert import Alert

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


@app.route(route="health", methods=["GET"])
def health(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps({"status": "ok"}),
        status_code=200,
        mimetype="application/json",
    )


def _parse_alert(req: func.HttpRequest) -> Alert:
    """Parse the request body into an Alert (raises on invalid payload)."""
    try:
        body = req.get_json()
    except ValueError:
        body = {}

    payload = DEMO_ALERT_PAYLOAD if body.get("demo") else body
    return Alert.from_azure_payload(payload)


@app.route(route="triage", methods=["POST"])
def triage(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP-triggered incident triage using the legacy monolithic agent."""
    return _handle_triage_request(req, run_triage, agent_label="IncidentTriageAgent")


@app.route(route="orchestrate", methods=["POST"])
def orchestrate(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP-triggered incident triage using the multi-agent OrchestratorAgent pipeline."""
    return _handle_triage_request(req, run_orchestrated, agent_label="OrchestratorAgent")


def _handle_triage_request(req: func.HttpRequest, run_fn, agent_label: str) -> func.HttpResponse:
    try:
        alert = _parse_alert(req)
    except Exception as exc:  # noqa: BLE001 - surface parse errors to caller
        logger.exception("Failed to parse alert payload")
        return func.HttpResponse(
            json.dumps({"error": f"Invalid alert payload: {exc}"}),
            status_code=400,
            mimetype="application/json",
        )

    logger.info("[%s] Alert received: %s (%s)", agent_label, alert.title, alert.severity)

    try:
        result = run_fn(alert)
    except Exception as exc:  # noqa: BLE001 - return 500 with details
        logger.exception("%s failed", agent_label)
        return func.HttpResponse(
            json.dumps({"error": f"{agent_label} failed: {exc}"}),
            status_code=500,
            mimetype="application/json",
        )

    return func.HttpResponse(
        json.dumps(result, default=str),
        status_code=200,
        mimetype="application/json",
    )
