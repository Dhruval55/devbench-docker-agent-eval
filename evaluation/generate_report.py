from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    report_path = Path("benchmark_report.json")
    if not report_path.exists():
        raise SystemExit("Run evaluation/run_benchmark.py first")
    rows = json.loads(report_path.read_text(encoding="utf-8"))
    lines = [
        "# Benchmark Report",
        "",
        "| Task | Status | Steps | Score | Time |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['task']} | {row['status']} | {row['steps']} | "
            f"{row['score']} | {row['elapsed_seconds']}s |"
        )
    Path("BENCHMARK_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

