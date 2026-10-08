from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.agent import GroqReactAgent, MockAgent
from agent.docker_runner import LocalRunner
from agent.logger import TrajectoryLogger
from evaluation.task_specs import TASKS, seed_workspace


def make_agent(name: str):
    if name == "mock":
        return MockAgent()
    if name == "groq":
        return GroqReactAgent()
    raise ValueError(f"unknown agent: {name}")


def run(agent_name: str, task_ids: list[str] | None = None) -> list[dict[str, object]]:
    agent = make_agent(agent_name)
    logger = TrajectoryLogger()
    selected = task_ids or list(TASKS)
    results: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="devbench_") as tmp:
        base = Path(tmp)
        for task_id in selected:
            workspace = base / task_id
            spec = seed_workspace(task_id, workspace)
            started = time.perf_counter()
            agent_result = agent.solve(spec, LocalRunner(str(workspace)), str(workspace))
            verdict = spec.verify(workspace)
            elapsed = time.perf_counter() - started
            summary = {
                "task": task_id,
                "status": "pass" if verdict.passed else "fail",
                "score": verdict.score,
                "steps": len(agent_result.events),
                "elapsed_seconds": round(elapsed, 3),
                "message": verdict.message,
            }
            logger.write(task_id, agent.name, agent_result.events, summary)
            results.append(summary)
    Path("benchmark_report.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    return results


def print_table(results: list[dict[str, object]]) -> None:
    print("Task                         Status  Steps  Score  Time(s)  Message")
    print("-" * 86)
    for row in results:
        print(
            f"{row['task']:<28} {row['status']:<7} {row['steps']:<5} "
            f"{row['score']:<5} {row['elapsed_seconds']:<7} {row['message']}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run DevBench-Docker benchmark")
    parser.add_argument("--agent", choices=["mock", "groq"], default="mock")
    parser.add_argument("--task", action="append", choices=list(TASKS), help="Run a single task; repeatable")
    args = parser.parse_args()
    results = run(args.agent, args.task)
    print_table(results)
    failed = [row for row in results if row["status"] != "pass"]
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()

