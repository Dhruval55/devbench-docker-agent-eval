from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

from agent.docker_runner import CommandResult
from agent.logger import TrajectoryEvent
from evaluation.task_specs import TaskSpec


class Runner(Protocol):
    def bash(self, command: str) -> CommandResult:
        ...


@dataclass
class AgentResult:
    submitted: bool
    events: list[TrajectoryEvent]


class StepBudgetExceeded(RuntimeError):
    pass


class MockAgent:
    """Offline deterministic agent that applies known-good task fixes."""

    name = "mock"

    def __init__(self, max_steps: int = 15) -> None:
        self.max_steps = max_steps

    def solve(self, spec: TaskSpec, runner: Runner, workspace: str) -> AgentResult:
        events: list[TrajectoryEvent] = []
        commands = spec.solution_commands(workspace)
        if len(commands) > self.max_steps:
            raise StepBudgetExceeded(f"{spec.task_id} needs {len(commands)} steps, budget is {self.max_steps}")
        for index, command in enumerate(commands, start=1):
            result = runner.bash(command)
            events.append(
                TrajectoryEvent(
                    step=index,
                    tool="bash",
                    command=command,
                    stdout=result.stdout[-4000:],
                    stderr=result.stderr[-4000:],
                    returncode=result.returncode,
                )
            )
            if result.returncode != 0:
                return AgentResult(submitted=False, events=events)
        return AgentResult(submitted=True, events=events)


class GroqReactAgent:
    """Minimal Groq ReAct wrapper.

    This project ships with a mock agent for reproducible CI. The Groq agent is
    deliberately small but functional: it asks the model for shell commands and
    stops when the model emits SUBMIT.
    """

    name = "groq"

    def __init__(self, model: str = "llama-3.3-70b-versatile", max_steps: int = 15) -> None:
        self.model = model
        self.max_steps = max_steps

    def solve(self, spec: TaskSpec, runner: Runner, workspace: str) -> AgentResult:
        try:
            from groq import Groq
        except ImportError as exc:
            raise RuntimeError("Install groq or use --agent mock") from exc
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is required for --agent groq")

        client = Groq(api_key=api_key)
        transcript = [
            {
                "role": "system",
                "content": (
                    "You are solving a containerized engineering task. "
                    "Reply with exactly one shell command per message, or SUBMIT when done."
                ),
            },
            {"role": "user", "content": spec.instructions},
        ]
        events: list[TrajectoryEvent] = []
        for step in range(1, self.max_steps + 1):
            response = client.chat.completions.create(model=self.model, messages=transcript, temperature=0)
            command = response.choices[0].message.content.strip()
            if command == "SUBMIT":
                return AgentResult(submitted=True, events=events)
            result = runner.bash(command)
            events.append(TrajectoryEvent(step, "bash", command, result.stdout[-4000:], result.stderr[-4000:], result.returncode))
            transcript.append({"role": "assistant", "content": command})
            transcript.append(
                {
                    "role": "user",
                    "content": f"returncode={result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}",
                }
            )
        return AgentResult(submitted=False, events=events)

