"""Tests for PowerShell tool execution safeguards."""

from tools.powershell_tools import PowerShellToolRunner


def test_runner_rejects_unapproved_script() -> None:
    runner = PowerShellToolRunner("scripts/powershell")
    result = runner.run("../../evil.ps1")
    assert result["status"] == "error"
    assert result["reason"] == "script_not_allowed"
