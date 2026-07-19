"""PowerShell script execution utilities for function-tool style usage."""

from __future__ import annotations

import shutil
import subprocess
from typing import Any


class PowerShellToolRunner:
    """Runs PowerShell scripts using pwsh (PowerShell Core)."""

    def __init__(self, script_root: str = "scripts/powershell") -> None:
        self._script_root = script_root

    @staticmethod
    def is_available() -> bool:
        """Return True if pwsh is installed in PATH."""

        return shutil.which("pwsh") is not None

    def run(self, script_name: str, args: list[str] | None = None) -> dict[str, Any]:
        """Execute a script and return structured output."""

        if not self.is_available():
            return {"status": "skipped", "reason": "pwsh_not_available", "stdout": "", "stderr": ""}

        script_path = f"{self._script_root.rstrip('/')}/{script_name}"
        cmd = ["pwsh", "-NoProfile", "-File", script_path, *(args or [])]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return {
            "status": "success" if result.returncode == 0 else "error",
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
