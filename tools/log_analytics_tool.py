"""
tools/log_analytics_tool.py
----------------------------
MAF Tool: Query Azure Log Analytics for context around an alert.

Queries:
  - Recent errors/exceptions from the affected resource.
  - CPU / memory metrics (if available via Heartbeat/Perf tables).
  - Recent Azure Activity Log entries for the resource.

Auth: DefaultAzureCredential.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Dict, List, Optional

from config.settings import settings

logger = logging.getLogger(__name__)


class LogAnalyticsTool:
    """Fetch diagnostic context from Azure Log Analytics."""

    def __init__(self) -> None:
        from azure.identity import DefaultAzureCredential  # lazy import
        from azure.monitor.query import LogsQueryClient  # lazy import
        credential = DefaultAzureCredential()
        self._client = LogsQueryClient(credential)
        self._workspace_id = settings.log_analytics_workspace_id

    def get_recent_errors(
        self,
        resource_name: str,
        lookback_hours: int = 1,
        limit: int = 20,
    ) -> List[Dict]:
        """Return recent error/exception log entries for a resource."""
        kql = f"""
        union AppExceptions, AzureDiagnostics, ContainerLog, KubeEvents
        | where TimeGenerated >= ago({lookback_hours}h)
        | where ResourceGroup =~ '{resource_name}' 
            or Computer has '{resource_name}' 
            or _ResourceId has '{resource_name}'
        | where SeverityLevel == "error" or Level == "Error" or Reason == "Failed"
        | project TimeGenerated, Type, Level, Message, ResourceId=_ResourceId
        | top {limit} by TimeGenerated desc
        """
        return self._run_query(kql, lookback_hours)

    def get_resource_health_events(
        self,
        resource_id: str,
        lookback_hours: int = 2,
    ) -> List[Dict]:
        """Return Azure Activity Log events for a specific resource."""
        kql = f"""
        AzureActivity
        | where TimeGenerated >= ago({lookback_hours}h)
        | where _ResourceId =~ '{resource_id}' or ResourceId =~ '{resource_id}'
        | where ActivityStatusValue in ('Failed', 'Warning', 'Critical')
        | project TimeGenerated, OperationNameValue, ActivityStatusValue, 
                  Caller, Properties
        | order by TimeGenerated desc
        """
        return self._run_query(kql, lookback_hours)

    def get_cpu_memory_trend(
        self,
        resource_name: str,
        lookback_hours: int = 1,
    ) -> List[Dict]:
        """Return CPU/memory trend for a VM or node."""
        kql = f"""
        Perf
        | where TimeGenerated >= ago({lookback_hours}h)
        | where Computer has '{resource_name}'
        | where CounterName in ('% Processor Time', 'Available MBytes')
        | summarize avg(CounterValue) by bin(TimeGenerated, 5m), CounterName
        | order by TimeGenerated desc
        """
        return self._run_query(kql, lookback_hours)

    def _run_query(self, kql: str, lookback_hours: int) -> List[Dict]:
        from azure.monitor.query import LogsQueryStatus  # lazy import
        if not self._workspace_id:
            logger.warning("LOG_ANALYTICS_WORKSPACE_ID not set — skipping query")
            return []
        try:
            response = self._client.query_workspace(
                workspace_id=self._workspace_id,
                query=kql,
                timespan=timedelta(hours=lookback_hours),
            )
            if response.status == LogsQueryStatus.SUCCESS:
                rows = []
                for table in response.tables:
                    cols = [col.name for col in table.columns]
                    for row in table.rows:
                        rows.append(dict(zip(cols, row)))
                return rows
            else:
                logger.warning("Log Analytics query partial/failed: %s", response.partial_error)
                return []
        except Exception as exc:
            logger.error("Log Analytics query error: %s", exc)
            return []

    def close(self) -> None:
        self._client.close()
