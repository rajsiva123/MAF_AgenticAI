"""
tools/resource_graph_tool.py
-----------------------------
MAF Tool: Query Azure Resource Graph for resource state and relationships.

Provides current resource properties, compliance, and linked resources
to give the LLM richer context for triage decisions.

Auth: DefaultAzureCredential.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from config.settings import settings

logger = logging.getLogger(__name__)


class ResourceGraphTool:
    """Fetch resource state and metadata from Azure Resource Graph."""

    def __init__(self) -> None:
        from azure.identity import DefaultAzureCredential  # lazy import
        from azure.mgmt.resourcegraph import ResourceGraphClient  # lazy import
        credential = DefaultAzureCredential()
        self._rg_client = ResourceGraphClient(credential)
        self._subscription_id = settings.subscription_id

    def get_resource_details(self, resource_id: str) -> Dict[str, Any]:
        """Return properties and tags of a resource by ARM resource ID."""
        query = f"""
        resources
        | where id =~ '{resource_id}'
        | project id, name, type, location, resourceGroup,
                  properties, tags, sku, zones
        """
        results = self._query(query)
        return results[0] if results else {}

    def get_related_resources(
        self, resource_group: str, resource_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List all resources in the same resource group (optionally filtered by type)."""
        type_filter = f"| where type =~ '{resource_type}'" if resource_type else ""
        query = f"""
        resources
        | where resourceGroup =~ '{resource_group}'
          and subscriptionId =~ '{self._subscription_id}'
        {type_filter}
        | project id, name, type, location, properties.provisioningState
        | limit 50
        """
        return self._query(query)

    def get_vm_instance_view(self, resource_group: str, vm_name: str) -> Dict[str, Any]:
        """Return VM power state and status from instance view."""
        try:
            compute_client = self._get_compute_client()
            instance_view = compute_client.virtual_machines.instance_view(
                resource_group, vm_name
            )
            statuses = [
                {"code": s.code, "displayStatus": s.display_status}
                for s in (instance_view.statuses or [])
            ]
            return {"vm_name": vm_name, "statuses": statuses}
        except Exception as exc:
            logger.error("Failed to get VM instance view for %s: %s", vm_name, exc)
            return {}

    def _query(self, kql: str) -> List[Dict[str, Any]]:
        from azure.mgmt.resourcegraph.models import QueryRequest  # lazy import
        try:
            request = QueryRequest(
                subscriptions=[self._subscription_id],
                query=kql,
            )
            response = self._rg_client.resources(request)
            data = response.data
            # Depending on API/result-format, `data` is either a list of dicts
            # (objectArray, default in newer API versions) or a table object
            # with .columns / .rows (table format).
            if isinstance(data, list):
                return data
            cols = [col.name for col in data.columns]
            return [dict(zip(cols, row)) for row in data.rows]
        except Exception as exc:
            logger.error("Resource Graph query error: %s", exc)
            return []

    def _get_compute_client(self):
        from azure.mgmt.compute import ComputeManagementClient
        from azure.identity import DefaultAzureCredential
        return ComputeManagementClient(DefaultAzureCredential(), self._subscription_id)
