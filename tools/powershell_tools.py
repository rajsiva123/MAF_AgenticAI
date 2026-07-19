"""PowerShell script execution utilities for function-tool style usage."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
import re
from typing import Any


class PowerShellToolRunner:
    """Runs PowerShell scripts using pwsh (PowerShell Core)."""

    def __init__(self, script_root: str = "scripts/powershell", execution_timeout_seconds: int = 60) -> None:
        self._script_root = Path(script_root).resolve()
        self._allowed_scripts = {"reset_password.ps1", "restart_service.ps1", "check_disk_space.ps1"}
        self._execution_timeout_seconds = execution_timeout_seconds
        self._allowed_arg_pattern = re.compile(r"^[A-Za-z0-9_.:@-]+$")

    @staticmethod
    def is_available() -> bool:
        """Return True if pwsh is installed in PATH."""

        return shutil.which("pwsh") is not None

    def run(self, script_name: str, args: list[str] | None = None) -> dict[str, Any]:
        """Execute a script and return structured output."""

        if not self.is_available():
            return {"status": "skipped", "reason": "pwsh_not_available", "stdout": "", "stderr": ""}

        if script_name not in self._allowed_scripts:
            return {"status": "error", "reason": "script_not_allowed", "stdout": "", "stderr": ""}

        for arg in args or []:
            if not self._allowed_arg_pattern.fullmatch(arg):
                return {"status": "error", "reason": "invalid_argument", "stdout": "", "stderr": ""}

        script_path = (self._script_root / script_name).resolve()
        try:
            script_path.relative_to(self._script_root)
        except ValueError:
            return {"status": "error", "reason": "invalid_script_path", "stdout": "", "stderr": ""}

        cmd = ["pwsh", "-NoProfile", "-File", str(script_path), *(args or [])]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=self._execution_timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return {"status": "error", "reason": "script_timeout", "stdout": "", "stderr": ""}
        return {
            "status": "success" if result.returncode == 0 else "error",
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
