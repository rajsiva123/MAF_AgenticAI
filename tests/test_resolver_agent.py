"""Tests for resolver flow with mocked PowerShell behavior."""

from pathlib import Path

from agents.resolver_agent import ResolverAgent
from tools.kb_search import KBSearch
from tools.powershell_tools import PowerShellToolRunner


class DummyRunner(PowerShellToolRunner):
    def __init__(self) -> None:
        super().__init__(script_root="unused")

    def run(self, script_name: str, args=None):
        return {"status": "success", "script": script_name}


def test_resolver_uses_kb_when_no_tool_match(tmp_path: Path) -> None:
    kb_dir = tmp_path / "kb"
    kb_dir.mkdir()
    (kb_dir / "vpn.md").write_text("VPN troubleshooting steps", encoding="utf-8")

    resolver = ResolverAgent(KBSearch(str(kb_dir)), DummyRunner())
    result = resolver.resolve("Need VPN troubleshooting")

    assert result.resolved is True
    assert "vpn.md" in result.resolution


def test_resolver_password_runs_powershell(tmp_path: Path) -> None:
    kb_dir = tmp_path / "kb"
    kb_dir.mkdir()
    (kb_dir / "password.md").write_text("password help", encoding="utf-8")

    resolver = ResolverAgent(KBSearch(str(kb_dir)), DummyRunner())
    result = resolver.resolve("Please reset my password")

    assert result.resolved is True
    assert result.evidence["tool"]["script"] == "reset_password.ps1"
