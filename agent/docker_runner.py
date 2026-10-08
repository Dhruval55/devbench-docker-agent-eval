from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass
class CommandResult:
    stdout: str
    stderr: str
    returncode: int


class DockerRunner:
    """Small docker exec adapter used by real agents.

    The mock benchmark uses a local filesystem runner so tests remain fast and
    deterministic. This class is intentionally thin: Docker isolation belongs to
    Docker, while verification remains host-side.
    """

    def __init__(self, container_name: str, timeout_seconds: int = 120) -> None:
        self.container_name = container_name
        self.timeout_seconds = timeout_seconds

    def bash(self, command: str) -> CommandResult:
        completed = subprocess.run(
            ["docker", "exec", self.container_name, "bash", "-lc", command],
            text=True,
            capture_output=True,
            timeout=self.timeout_seconds,
            check=False,
        )
        return CommandResult(completed.stdout, completed.stderr, completed.returncode)


class LocalRunner:
    """Filesystem-backed command runner used by tests and the mock agent."""

    def __init__(self, cwd: str, timeout_seconds: int = 120) -> None:
        self.cwd = cwd
        self.timeout_seconds = timeout_seconds

    def bash(self, command: str) -> CommandResult:
        completed = subprocess.run(
            command,
            cwd=self.cwd,
            shell=True,
            text=True,
            capture_output=True,
            timeout=self.timeout_seconds,
            check=False,
        )
        return CommandResult(completed.stdout, completed.stderr, completed.returncode)

