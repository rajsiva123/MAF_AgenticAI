"""
main.py
-------
Entry point for the MAF Cloud Incident Triage PoC.

Can be invoked:
  1. From the command line with a JSON alert file:
       python main.py --alert sample_alert.json
  2. As an Azure Function HTTP trigger (see azure_function_app/ for that variant).
  3. Programmatically by importing run_triage().

Usage examples:
  python main.py --alert sample_alert.json
  python main.py --demo          # runs with built-in demo alert
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from agents.incident_triage_agent import IncidentTriageAgent
from models.alert import Alert

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ── Demo alert (used with --demo flag) ───────────────────────────────
DEMO_ALERT_PAYLOAD = {
    "id": "demo-alert-001",
    "data": {
        "essentials": {
            "alertId": "demo-alert-001",
            "severity": "Sev2",
            "alertRule": "High CPU on aisupportengineer-func",
            "description": "CPU usage exceeded 90% for more than 5 minutes.",
            "alertTargetIDs": [
                "/subscriptions/bdd18b19-ee46-46a1-9b1e-fdc146ff55f0"
                "/resourceGroups/AIAgentRG"
                "/providers/Microsoft.Web/sites/aisupportengineer-func"
            ],
        }
    },
}


def run_triage(alert: Alert) -> dict:
    """Run the triage agent on an Alert. Returns serialisable result dict."""
    agent = IncidentTriageAgent()
    result = agent.run(alert)
    return {
        "alert_id": result.alert.alert_id,
        "approved": result.approved,
        "actions_executed": result.actions_executed,
        "errors": result.errors,
        "summary": result.plan.summary if result.plan else "No plan generated.",
        "root_cause": result.plan.root_cause_hypothesis if result.plan else "",
        "confidence": result.plan.confidence_score if result.plan else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="MAF Cloud Incident Triage Agent")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--alert", type=Path, help="Path to JSON alert file")
    group.add_argument("--demo", action="store_true", help="Run with built-in demo alert")
    args = parser.parse_args()

    if args.demo:
        payload = DEMO_ALERT_PAYLOAD
    else:
        payload = json.loads(args.alert.read_text())

    alert = Alert.from_azure_payload(payload)
    logger.info("Alert loaded: %s (%s)", alert.title, alert.severity)

    output = run_triage(alert)
    print("\n" + "═" * 60)
    print("TRIAGE RESULT")
    print("═" * 60)
    print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    main()
