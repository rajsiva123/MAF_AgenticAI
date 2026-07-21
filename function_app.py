"""
azure_function_app/function_app.py
-----------------------------------
Azure Functions (Python v2 programming model) entry point for the MAF
Cloud Incident Triage agent.

Exposes:
  POST /api/triage   - accepts an Azure Monitor common-alert-schema JSON body
                        (or a simplified {"demo": true} body) and runs the
                        IncidentTriageAgent synchronously, returning the
                        triage result as JSON.
  GET  /api/health    - simple liveness check.

This module reuses the existing project code (agents/, models/, llm/, tools/,
approval/, config/) which is packaged alongside this function app at deploy
time (see README / deploy instructions).
"""
from __future__ import annotations

import json
import logging

import azure.functions as func

from agents.incident_triage_agent import IncidentTriageAgent
from models.alert import Alert
from main import DEMO_ALERT_PAYLOAD, run_triage

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


@app.route(route="triage", methods=["POST"])
def triage(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP-triggered incident triage.

    Body: either a full Azure Monitor common alert schema payload, or
    {"demo": true} to use the built-in demo alert.
    """
    try:
        body = req.get_json()
    except ValueError:
        body = {}

    if body.get("demo"):
        payload = DEMO_ALERT_PAYLOAD
    else:
        payload = body

    try:
        alert = Alert.from_azure_payload(payload)
    except Exception as exc:  # noqa: BLE001 - surface parse errors to caller
        logger.exception("Failed to parse alert payload")
        return func.HttpResponse(
            json.dumps({"error": f"Invalid alert payload: {exc}"}),
            status_code=400,
            mimetype="application/json",
        )

    logger.info("Alert received: %s (%s)", alert.title, alert.severity)

    try:
        result = run_triage(alert)
    except Exception as exc:  # noqa: BLE001 - return 500 with details
        logger.exception("Triage agent failed")
        return func.HttpResponse(
            json.dumps({"error": f"Triage failed: {exc}"}),
            status_code=500,
            mimetype="application/json",
        )

    return func.HttpResponse(
        json.dumps(result, default=str),
        status_code=200,
        mimetype="application/json",
    )
