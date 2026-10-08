from __future__ import annotations

from pathlib import Path

import pytest

from agent.agent import MockAgent, StepBudgetExceeded
from agent.docker_runner import LocalRunner
from evaluation.task_specs import TASKS, seed_workspace


def test_mock_agent_solves_all_tasks(tmp_path: Path) -> None:
    for task_id in TASKS:
        spec = seed_workspace(task_id, tmp_path / task_id)
        result = MockAgent().solve(spec, LocalRunner(str(tmp_path / task_id)), str(tmp_path / task_id))
        verdict = spec.verify(tmp_path / task_id)
        assert result.submitted
        assert verdict.passed


def test_step_budget_is_enforced(tmp_path: Path) -> None:
    spec = seed_workspace("task_1_nginx_fix", tmp_path / "task")
    with pytest.raises(StepBudgetExceeded):
        MockAgent(max_steps=0).solve(spec, LocalRunner(str(tmp_path / "task")), str(tmp_path / "task"))

