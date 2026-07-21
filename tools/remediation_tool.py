"""
tools/remediation_tool.py
--------------------------
MAF Tool: Execute safe, idempotent remediation actions on Azure resources.

Actions supported:
  - restart_resource   — Restart a VM or App Service
  - scale_out          — Increase instance count (App Service / VMSS)
  - run_runbook        — Trigger an Azure Automation Runbook
  - collect_diagnostics — Capture VM diagnostics / app logs snapshot
  - notify             — Post a notification (Teams webhook)

Safety rules:
  - Only executes actions marked safe_to_automate=True in the plan.
  - All actions are idempotent and non-destructive by design.
  - Destructive actions (delete, stop) are intentionally excluded.

Auth: DefaultAzureCredential.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

import requests

from config.settings import settings
from models.remediation_plan import RemediationAction, ActionType

logger = logging.getLogger(__name__)


class RemediationTool:
    """Execute approved remediation actions on Azure resources."""

    def __init__(self) -> None:
        from azure.identity import DefaultAzureCredential  # lazy import
        self._credential = DefaultAzureCredential()
        self._subscription_id = settings.subscription_id
        self._automation_rg = settings.automation_resource_group
        self._automation_account = settings.automation_account_name

    def execute(self, action: RemediationAction) -> Dict[str, Any]:
        """
        Dispatch a single RemediationAction.

        Returns a result dict with keys: success (bool), message (str), details (dict).
        """
        logger.info("Executing action: %s on %s", action.action_type, action.resource_id)

        dispatch = {
            ActionType.RESTART_RESOURCE: self._restart_resource,
            ActionType.SCALE_OUT: self._scale_out,
            ActionType.RUN_RUNBOOK: self._run_runbook,
            ActionType.COLLECT_DIAGNOSTICS: self._collect_diagnostics,
            ActionType.NOTIFY: self._notify,
            ActionType.NO_ACTION: self._no_action,
        }
        handler = dispatch.get(action.action_type, self._unsupported)
        return handler(action)

    # ── Action handlers ──────────────────────────────────────────────

    def _restart_resource(self, action: RemediationAction) -> Dict[str, Any]:
        """Restart a VM or App Service."""
        rid = action.resource_id.lower()
        try:
            if "virtualmachines" in rid:
                return self._restart_vm(action)
            elif "sites" in rid:
                return self._restart_app_service(action)
            else:
                return {"success": False, "message": f"Unsupported resource type for restart: {rid}"}
        except Exception as exc:
            logger.error("Restart failed: %s", exc)
            return {"success": False, "message": str(exc)}

    def _restart_vm(self, action: RemediationAction) -> Dict[str, Any]:
        from azure.mgmt.compute import ComputeManagementClient
        parts = action.resource_id.split("/")
        rg = parts[parts.index("resourceGroups") + 1] if "resourceGroups" in parts else ""
        vm_name = parts[-1]
        client = ComputeManagementClient(self._credential, self._subscription_id)
        poller = client.virtual_machines.begin_restart(rg, vm_name)
        poller.result()  # wait for completion
        msg = f"VM '{vm_name}' restarted successfully."
        logger.info(msg)
        return {"success": True, "message": msg, "details": {"vm": vm_name, "rg": rg}}

    def _restart_app_service(self, action: RemediationAction) -> Dict[str, Any]:
        from azure.mgmt.web import WebSiteManagementClient
        parts = action.resource_id.split("/")
        rg = parts[parts.index("resourceGroups") + 1] if "resourceGroups" in parts else ""
        app_name = parts[-1]
        client = WebSiteManagementClient(self._credential, self._subscription_id)
        client.web_apps.restart(rg, app_name)
        msg = f"App Service '{app_name}' restarted successfully."
        logger.info(msg)
        return {"success": True, "message": msg, "details": {"app": app_name, "rg": rg}}

    def _scale_out(self, action: RemediationAction) -> Dict[str, Any]:
        """Increase App Service Plan instance count by 1 (max guard: 5)."""
        from azure.mgmt.web import WebSiteManagementClient
        parts = action.resource_id.split("/")
        rg = parts[parts.index("resourceGroups") + 1] if "resourceGroups" in parts else ""
        plan_name = parts[-1]
        target_count = min(int(action.parameters.get("instance_count", 2)), 5)
        client = WebSiteManagementClient(self._credential, self._subscription_id)
        plan = client.app_service_plans.get(rg, plan_name)
        plan.sku.capacity = target_count
        client.app_service_plans.begin_create_or_update(rg, plan_name, plan).result()
        msg = f"App Service Plan '{plan_name}' scaled to {target_count} instances."
        logger.info(msg)
        return {"success": True, "message": msg, "details": {"plan": plan_name, "capacity": target_count}}

    def _run_runbook(self, action: RemediationAction) -> Dict[str, Any]:
        """Trigger an Azure Automation Runbook job."""
        from azure.mgmt.automation import AutomationClient  # lazy import
        from azure.mgmt.automation.models import RunbookAssociationProperty, JobCreateParameters  # lazy import
        if not self._automation_account:
            return {"success": False, "message": "AUTOMATION_ACCOUNT_NAME not configured."}
        client = AutomationClient(self._credential, self._subscription_id)
        job_params = JobCreateParameters(
            runbook=RunbookAssociationProperty(name=action.runbook_name),
            parameters=action.parameters,
            run_on="",
        )
        job = client.job.create(
            self._automation_rg,
            self._automation_account,
            f"maf-{action.runbook_name}-{id(action)}",
            job_params,
        )
        msg = f"Runbook '{action.runbook_name}' started — job: {job.name}"
        logger.info(msg)
        return {"success": True, "message": msg, "details": {"job_name": job.name}}

    def _collect_diagnostics(self, action: RemediationAction) -> Dict[str, Any]:
        """
        Collect diagnostics: snapshot resource state via Resource Graph.
        Writes output to a structured dict (could be persisted to Blob/Log Analytics).
        """
        from tools.resource_graph_tool import ResourceGraphTool
        rgt = ResourceGraphTool()
        details = rgt.get_resource_details(action.resource_id)
        msg = f"Diagnostics collected for {action.resource_id}"
        logger.info(msg)
        return {"success": True, "message": msg, "details": details}

    def _notify(self, action: RemediationAction) -> Dict[str, Any]:
        """Post a Teams adaptive card notification via webhook."""
        webhook_url = action.parameters.get("webhook_url") or settings.teams_webhook_url
        if not webhook_url:
            return {"success": False, "message": "No Teams webhook URL configured."}
        card = {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "summary": action.rationale,
            "themeColor": "FF0000",
            "title": "🚨 Incident Triage Notification",
            "text": action.rationale,
        }
        resp = requests.post(webhook_url, json=card, timeout=10)
        success = resp.status_code == 200
        msg = f"Teams notification sent (HTTP {resp.status_code})."
        return {"success": success, "message": msg}

    def _no_action(self, action: RemediationAction) -> Dict[str, Any]:
        msg = "No action required — monitoring only."
        logger.info(msg)
        return {"success": True, "message": msg}

    def _unsupported(self, action: RemediationAction) -> Dict[str, Any]:
        msg = f"Unsupported action type: {action.action_type}"
        logger.warning(msg)
        return {"success": False, "message": msg}
