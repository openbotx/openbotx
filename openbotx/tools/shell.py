import asyncio
import os
import re
from pathlib import Path
from typing import Any

from openbotx.tools.base import Tool


class ExecTool(Tool):
    """Shell command execution with safety guards."""

    name = "exec"
    description = "Execute a shell command and return its output."
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to execute",
            },
            "working_dir": {
                "type": "string",
                "description": "Optional working directory",
            },
        },
        "required": ["command"],
    }

    _MAX_OUTPUT = 200_000  # 200KB

    _DENY_PATTERNS = [
        # destructive file operations
        r"\brm\s+-[rf]{1,2}\b",
        r"\bdel\s+/[fq]\b",
        r"\brmdir\s+/s\b",
        r"\b(shred|srm|wipe)\b",
        r"\btruncate\s+-s\s*0\b",
        r"\bfind\b.*\s(-delete|-exec\s+rm)\b",
        # disk/system destruction
        r"(?:^|[;&|]\s*)format\b",
        r"\b(mkfs|diskpart)\b",
        r"\bdd\s+if=",
        r">\s*/dev/(sd|nvme|loop|mem|kmem)",
        r"\b(shutdown|reboot|poweroff|halt|init\s+[06])\b",
        r":\(\)\s*\{.*\};\s*:",
        # encoding/pipe tricks
        r"\bbase64\b.*\s-[dD]\b",
        r"\beval\b\s",
        r"\bcurl\b.*\|\s*(?:sh|bash|zsh)\b",
        r"\bwget\b.*\|\s*(?:sh|bash|zsh)\b",
        r"\bpython[23]?\b.*\|\s*(?:sh|bash)\b",
        # subshell/command substitution
        r"\$\([^)]+\)",
        r"`[^`]+`",
        # process substitution
        r"<\(",
        r">\(",
        # environment injection
        r"\b(ld_preload|ld_library_path|dyld_insert_libraries)\s*=",
        r"\b(prompt_command|ps4)\s*=",
        # dangerous redirects
        r">\s*/etc/",
        r">\s*/proc/",
        r">\s*/sys/",
        r">\s*/dev/",
    ]

    def __init__(
        self,
        timeout: int = 60,
        working_dir: str | None = None,
        restrict_to_workspace: bool = True,
    ):
        self.timeout = timeout
        self.working_dir = working_dir
        self.restrict_to_workspace = restrict_to_workspace

    async def execute(self, command: str, working_dir: str | None = None, **kwargs: Any) -> str:
        cwd = working_dir or self.working_dir or os.getcwd()
        guard_error = self._guard_command(command, cwd)
        if guard_error:
            return guard_error

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )

            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=self.timeout)
            except TimeoutError:
                process.kill()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except TimeoutError:
                    pass
                return f"Error: Command timed out after {self.timeout} seconds"

            output_parts = []
            if stdout:
                output_parts.append(stdout.decode("utf-8", errors="replace"))
            if stderr:
                stderr_text = stderr.decode("utf-8", errors="replace")
                if stderr_text.strip():
                    output_parts.append(f"STDERR:\n{stderr_text}")
            if process.returncode != 0:
                output_parts.append(f"\nExit code: {process.returncode}")

            result = "\n".join(output_parts) if output_parts else "(no output)"

            if len(result) > self._MAX_OUTPUT:
                result = (
                    f"[Output truncated: showing last {self._MAX_OUTPUT} of {len(result)} chars]\n"
                    + result[-self._MAX_OUTPUT :]
                )
            return result

        except Exception as e:
            return f"Error executing command: {e}"

    def _guard_command(self, command: str, cwd: str) -> str | None:
        lower = command.strip().lower()

        for pattern in self._DENY_PATTERNS:
            if re.search(pattern, lower):
                return "Error: Command blocked by safety guard (dangerous pattern detected)"

        # detect ANSI-C quoting with hex, octal, or unicode escapes (bypass attempt)
        if re.search(r"\$'[^']*\\(x[0-9a-f]|[0-7]{2,3}|u[0-9a-f])", lower):
            return "Error: Command blocked by safety guard (encoded escape detected)"

        if self.restrict_to_workspace:
            if "..\\" in command or "../" in command:
                return "Error: Command blocked by safety guard (path traversal detected)"

            cwd_path = Path(cwd).resolve()
            posix_paths = re.findall(r"(?:^|[\s|>])(/[^\s\"'>]+)", command)
            for raw in posix_paths:
                try:
                    p = Path(raw.strip()).resolve()
                except Exception:
                    continue
                if p.is_absolute() and cwd_path not in p.parents and p != cwd_path:
                    return "Error: Command blocked by safety guard (path outside working dir)"

        return None
