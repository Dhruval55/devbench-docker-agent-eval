# DevBench-Docker

Containerized AI agent evaluation harness with deterministic host-side verifiers and negative tests for reward-hacking resistance.

## What This Demonstrates

- Sandboxed ReAct-style agent harness with step budgets and trajectory logging.
- Host-side deterministic graders that reject do-nothing, tampered, and partial solutions.
- Six realistic engineering tasks: Nginx config repair, pytest bug fix, log triage, SQLite migration repair, dependency conflict resolution, and SSH permission lockdown.
- Offline mock agent for CI plus optional Groq/Llama agent integration.

## Quick Start

```bash
python -m pip install -r requirements.txt
python -m pytest
python evaluation/run_benchmark.py --agent mock
```

The benchmark writes:

- `benchmark_report.json`
- `trajectories/<task>_mock.json`

## Optional Groq Run

```bash
copy .env.example .env
set GROQ_API_KEY=your_key_here
python evaluation/run_benchmark.py --agent groq --task task_2_pytest_repair
```

## Docker

```bash
docker compose up --build
```

## Architecture

```text
agent/                 ReAct agents, Docker command adapter, trajectory logger
evaluation/            Task registry, benchmark runner, report generation
tasks/                 Task-facing Dockerfiles, prompts, and grader entrypoints
tests/                 Negative verifier and harness unit tests
.github/workflows/     CI for tests and mock benchmark
```

## Security Model

Agents operate on task workspaces. Graders are invoked outside the agent context and inspect the resulting filesystem state directly. The negative verifier suite proves that every grader fails fresh workspaces, visible reward-hacking artifacts, and partial fixes before accepting the known-good repair.

