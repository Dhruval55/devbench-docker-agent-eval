from __future__ import annotations

from pathlib import Path

import pytest

from evaluation.task_specs import TASKS, seed_workspace, write


@pytest.mark.parametrize("task_id", list(TASKS))
def test_fresh_task_fails_do_nothing(tmp_path: Path, task_id: str) -> None:
    spec = seed_workspace(task_id, tmp_path / task_id)
    result = spec.verify(tmp_path / task_id)
    assert not result.passed
    assert result.score == 0.0


@pytest.mark.parametrize("task_id", list(TASKS))
def test_reward_hacking_artifacts_fail(tmp_path: Path, task_id: str) -> None:
    spec = seed_workspace(task_id, tmp_path / task_id)
    write(tmp_path / task_id / ".reward_hack", "exit 0\n")
    result = spec.verify(tmp_path / task_id)
    assert not result.passed
    assert "tampering" in result.message


@pytest.mark.parametrize("task_id", list(TASKS))
def test_partial_solution_fails(tmp_path: Path, task_id: str) -> None:
    spec = seed_workspace(task_id, tmp_path / task_id)
    spec.partial(tmp_path / task_id)
    result = spec.verify(tmp_path / task_id)
    assert not result.passed
    assert result.score == 0.0


@pytest.mark.parametrize("task_id", list(TASKS))
def test_known_good_solution_passes(tmp_path: Path, task_id: str) -> None:
    spec = seed_workspace(task_id, tmp_path / task_id)
    from agent.docker_runner import LocalRunner

    runner = LocalRunner(str(tmp_path / task_id))
    for command in spec.solution_commands(str(tmp_path / task_id)):
        completed = runner.bash(command)
        assert completed.returncode == 0, completed.stderr
    result = spec.verify(tmp_path / task_id)
    assert result.passed
    assert result.score == 1.0

