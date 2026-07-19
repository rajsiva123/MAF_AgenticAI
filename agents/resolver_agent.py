"""Resolver agent that uses KB retrieval and PowerShell-backed tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tools.kb_search import KBSearch
from tools.powershell_tools import PowerShellToolRunner

DEFAULT_DEMO_USERNAME = "demo.user"
DEFAULT_SERVICE_NAME = "Spooler"


@dataclass
class ResolverResult:
    """Resolver output consumed by orchestration layer."""

    resolved: bool
    resolution: str
    evidence: dict[str, Any]


class ResolverAgent:
    """Attempts auto-resolution using KB and lightweight automation tools."""

    def __init__(self, kb_search: KBSearch, powershell_runner: PowerShellToolRunner) -> None:
        self._kb_search = kb_search
        self._powershell_runner = powershell_runner

    def resolve(self, message: str) -> ResolverResult:
        """Attempt to resolve a service desk issue."""

        text = message.lower()
        kb_hits = self._kb_search.search(message)

        if "password" in text:
            tool_result = self._powershell_runner.run("reset_password.ps1", ["-UserName", DEFAULT_DEMO_USERNAME])
            success = tool_result.get("status") in {"success", "skipped"}
            return ResolverResult(
                resolved=success,
                resolution="Password reset workflow executed" if success else "Password reset failed",
                evidence={"kb_hits": [hit.source for hit in kb_hits], "tool": tool_result},
            )

        if "restart" in text or "service" in text:
            tool_result = self._powershell_runner.run("restart_service.ps1", ["-ServiceName", DEFAULT_SERVICE_NAME])
            success = tool_result.get("status") in {"success", "skipped"}
            return ResolverResult(
                resolved=success,
                resolution="Service restart workflow executed" if success else "Service restart failed",
                evidence={"kb_hits": [hit.source for hit in kb_hits], "tool": tool_result},
            )

        if kb_hits:
            return ResolverResult(
                resolved=True,
                resolution=f"Suggested KB article: {kb_hits[0].source}",
                evidence={"kb_hits": [hit.source for hit in kb_hits]},
            )

        return ResolverResult(
            resolved=False,
            resolution="No automatic resolution found",
            evidence={"kb_hits": []},
        )
