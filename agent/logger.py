from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class TrajectoryEvent:
    step: int
    tool: str
    command: str
    stdout: str
    stderr: str
    returncode: int


class TrajectoryLogger:
    def __init__(self, output_dir: Path = Path("trajectories")) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write(self, task_id: str, agent_name: str, events: list[TrajectoryEvent], summary: dict[str, Any]) -> Path:
        path = self.output_dir / f"{task_id}_{agent_name}.json"
        payload = {
            "task_id": task_id,
            "agent": agent_name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "events": [asdict(event) for event in events],
            "summary": summary,
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

