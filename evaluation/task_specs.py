from __future__ import annotations

import json
import os
import shutil
import sqlite3
from hashlib import sha256
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class VerifyResult:
    passed: bool
    score: float
    message: str
    details: dict[str, Any] | None = None


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    title: str
    category: str
    difficulty: str
    instructions: str
    seed: Callable[[Path], None]
    verify: Callable[[Path], VerifyResult]
    solution_commands: Callable[[str], list[str]]
    partial: Callable[[Path], None]


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    write(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def file_hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def create_host_oracle(root: Path, payload: dict[str, Any]) -> None:
    oracle = root / ".devbench" / "oracle.json"
    write_json(oracle, payload)
    manifest = {
        "protected_files": {
            ".devbench/oracle.json": file_hash(oracle),
        }
    }
    write_json(root / ".devbench" / "manifest.json", manifest)


def verify_host_oracle(root: Path) -> tuple[dict[str, Any] | None, VerifyResult | None]:
    manifest_path = root / ".devbench" / "manifest.json"
    oracle_path = root / ".devbench" / "oracle.json"
    if not manifest_path.exists() or not oracle_path.exists():
        return None, VerifyResult(False, 0.0, "host oracle or manifest missing")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        oracle = json.loads(oracle_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, VerifyResult(False, 0.0, f"host verifier metadata corrupted: {exc}")
    for relative, expected_hash in manifest.get("protected_files", {}).items():
        protected = root / relative
        if not protected.exists():
            return None, VerifyResult(False, 0.0, f"protected verifier file missing: {relative}")
        if file_hash(protected) != expected_hash:
            return None, VerifyResult(False, 0.0, f"protected verifier file changed: {relative}")
    return oracle, None


def set_expected_mode(root: Path, path: Path, mode: int) -> None:
    try:
        os.chmod(path, mode)
    except OSError:
        pass
    metadata = root / ".devbench_modes.json"
    modes = json.loads(metadata.read_text(encoding="utf-8")) if metadata.exists() else {}
    modes[str(path.relative_to(root)).replace("\\", "/")] = mode
    metadata.write_text(json.dumps(modes, sort_keys=True), encoding="utf-8")


def read_expected_mode(root: Path, path: Path) -> int:
    metadata = root / ".devbench_modes.json"
    key = str(path.relative_to(root)).replace("\\", "/")
    if metadata.exists():
        modes = json.loads(metadata.read_text(encoding="utf-8"))
        if key in modes:
            return int(modes[key])
    return path.stat().st_mode & 0o777


def require_no_tamper(root: Path) -> VerifyResult | None:
    forbidden = [
        root / "grader.py",
        root / "tests" / "test_graders_negative.py",
        root / ".reward_hack",
    ]
    for path in forbidden:
        if path.exists():
            return VerifyResult(False, 0.0, f"tampering artifact detected: {path.relative_to(root)}")
    return None


def seed_nginx(root: Path) -> None:
    write(
        root / "etc" / "nginx" / "nginx.conf",
        """
events {}
http {
  upstream app_backend { server 127.0.0.1:9000; }
  server {
    listen 8080;
    location /api/ {
      proxy_pass http://app_backend
    }
  }
}
""".strip()
        + "\n",
    )
    create_host_oracle(
        root,
        {
            "must_contain": ["proxy_pass http://app_backend;", "listen 8080;", "location /api/"],
            "must_not_contain": ["proxy_pass http://app_backend\n"],
        },
    )


def verify_nginx(root: Path) -> VerifyResult:
    if tamper := require_no_tamper(root):
        return tamper
    oracle, oracle_error = verify_host_oracle(root)
    if oracle_error:
        return oracle_error
    conf = root / "etc" / "nginx" / "nginx.conf"
    if not conf.exists():
        return VerifyResult(False, 0.0, "nginx.conf missing")
    text = conf.read_text(encoding="utf-8")
    required = oracle["must_contain"]
    forbidden = oracle["must_not_contain"]
    details = {
        "required_present": {item: item in text for item in required},
        "forbidden_absent": {item: item not in text for item in forbidden},
    }
    score = (
        sum(details["required_present"].values()) + sum(details["forbidden_absent"].values())
    ) / (len(required) + len(forbidden))
    if score == 1.0:
        return VerifyResult(True, 1.0, "nginx reverse proxy config is syntactically repaired", details)
    return VerifyResult(False, 0.0, "nginx config still has missing proxy syntax or route", details)


def seed_pytest(root: Path) -> None:
    write(
        root / "src" / "utils.py",
        """
def nth_item(items, n):
    return items[n]


def middle(items):
    return nth_item(items, len(items) // 2)
""".strip()
        + "\n",
    )
    create_host_oracle(
        root,
        {
            "cases": [
                {"items": ["a", "b", "c"], "n": 1, "expected": "a"},
                {"items": ["a", "b", "c"], "n": 3, "expected": "c"},
                {"items": [10, 20, 30, 40], "n": 4, "expected": 40},
            ],
            "middle_cases": [
                {"items": [1, 2, 3], "expected": 2},
                {"items": ["left", "center", "right"], "expected": "center"},
            ],
        },
    )
    write(
        root / "tests" / "test_utils.py",
        """
from src.utils import nth_item, middle


def test_nth_item_uses_human_indexing():
    assert nth_item(["a", "b", "c"], 1) == "a"
    assert nth_item(["a", "b", "c"], 3) == "c"


def test_middle():
    assert middle([1, 2, 3]) == 2
""".strip()
        + "\n",
    )


def verify_pytest(root: Path) -> VerifyResult:
    if tamper := require_no_tamper(root):
        return tamper
    oracle, oracle_error = verify_host_oracle(root)
    if oracle_error:
        return oracle_error
    utils = root / "src" / "utils.py"
    if not utils.exists():
        return VerifyResult(False, 0.0, "src/utils.py missing")
    namespace: dict[str, object] = {}
    exec(utils.read_text(encoding="utf-8"), namespace)
    try:
        case_results = [
            namespace["nth_item"](case["items"], case["n"]) == case["expected"]
            for case in oracle["cases"]
        ]
        middle_results = [
            namespace["middle"](case["items"]) == case["expected"]
            for case in oracle["middle_cases"]
        ]
    except Exception as exc:
        return VerifyResult(False, 0.0, f"library still raises: {exc}")
    details = {"nth_item_cases": case_results, "middle_cases": middle_results}
    all_results = case_results + middle_results
    score = sum(all_results) / len(all_results)
    return (
        VerifyResult(True, 1.0, "indexing bug repaired", details)
        if score == 1.0
        else VerifyResult(False, 0.0, "indexing behavior still incorrect", details)
    )


def seed_logs(root: Path) -> None:
    write(
        root / "var" / "log" / "app.log",
        """
2026-01-01T10:00:00Z INFO boot ok
2026-01-01T10:01:00Z ERROR DB_TIMEOUT request_id=a1
2026-01-01T10:02:00Z WARN retrying
2026-01-01T10:03:00Z ERROR AUTH_FAILURE request_id=a2
2026-01-01T10:04:00Z ERROR DB_TIMEOUT request_id=a3
""".strip()
        + "\n",
    )
    create_host_oracle(
        root,
        {
            "summary": {
                "total_errors": 3,
                "error_counts": {"DB_TIMEOUT": 2, "AUTH_FAILURE": 1},
            }
        },
    )


def verify_logs(root: Path) -> VerifyResult:
    if tamper := require_no_tamper(root):
        return tamper
    oracle, oracle_error = verify_host_oracle(root)
    if oracle_error:
        return oracle_error
    summary = root / "output" / "summary.json"
    if not summary.exists():
        return VerifyResult(False, 0.0, "output/summary.json missing")
    try:
        data = json.loads(summary.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return VerifyResult(False, 0.0, f"summary is invalid JSON: {exc}")
    expected = oracle["summary"]
    if data == expected:
        return VerifyResult(True, 1.0, "log summary is correct", {"expected": expected, "actual": data})
    score = 0.0
    if data.get("total_errors") == expected["total_errors"]:
        score += 0.4
    if data.get("error_counts") == expected["error_counts"]:
        score += 0.6
    return VerifyResult(False, 0.0, "log summary mismatch", {"expected": expected, "actual": data})


def seed_db(root: Path) -> None:
    write(
        root / "migrations" / "001_create_schema.sql",
        """
PRAGMA foreign_keys = ON;
CREATE TABLE orders (
  id INTEGER PRIMARY KEY,
  customer_id INTEGER NOT NULL,
  total_cents INTEGER NOT NULL,
  FOREIGN KEY (customer_id) REFERENCES customers(id)
);
CREATE TABLE customers (
  customer_pk INTEGER PRIMARY KEY,
  email TEXT NOT NULL UNIQUE
);
""".strip()
        + "\n",
    )
    create_host_oracle(
        root,
        {
            "required_tables": ["customers", "orders"],
            "valid_order": {"customer_email": "dev@example.com", "total_cents": 1250},
            "invalid_customer_id": 999,
        },
    )


def verify_db(root: Path) -> VerifyResult:
    if tamper := require_no_tamper(root):
        return tamper
    oracle, oracle_error = verify_host_oracle(root)
    if oracle_error:
        return oracle_error
    sql_path = root / "migrations" / "001_create_schema.sql"
    if not sql_path.exists():
        return VerifyResult(False, 0.0, "migration missing")
    sql = sql_path.read_text(encoding="utf-8")
    try:
        conn = sqlite3.connect(":memory:")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(sql)
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not set(oracle["required_tables"]).issubset(tables):
            return VerifyResult(False, 0.0, "migration missing required tables", {"tables": sorted(tables)})
        conn.execute("INSERT INTO customers(email) VALUES (?)", (oracle["valid_order"]["customer_email"],))
        conn.execute(
            "INSERT INTO orders(customer_id, total_cents) VALUES (1, ?)",
            (oracle["valid_order"]["total_cents"],),
        )
        conn.execute(
            "INSERT INTO orders(customer_id, total_cents) VALUES (?, ?)",
            (oracle["invalid_customer_id"], oracle["valid_order"]["total_cents"]),
        )
    except sqlite3.IntegrityError:
        return VerifyResult(True, 1.0, "schema creates tables and enforces foreign keys", {"foreign_key_rejected": True})
    except sqlite3.Error as exc:
        return VerifyResult(False, 0.0, f"migration does not apply cleanly: {exc}")
    return VerifyResult(False, 0.0, "foreign key is not enforced")


def seed_deps(root: Path) -> None:
    write(root / "requirements.txt", "requests==2.31.0\nurllib3==1.20.0\n")
    create_host_oracle(
        root,
        {
            "pins": {"requests": "2.31.0"},
            "compatible_urllib3": ["urllib3==2.0.7", "urllib3>=1.21.1,<3"],
        },
    )


def verify_deps(root: Path) -> VerifyResult:
    if tamper := require_no_tamper(root):
        return tamper
    oracle, oracle_error = verify_host_oracle(root)
    if oracle_error:
        return oracle_error
    req = root / "requirements.txt"
    if not req.exists():
        return VerifyResult(False, 0.0, "requirements.txt missing")
    lines = {line.strip() for line in req.read_text(encoding="utf-8").splitlines() if line.strip()}
    has_requests = f"requests=={oracle['pins']['requests']}" in lines
    has_compatible_urllib3 = any(
        line.startswith("urllib3==2.") or line in oracle["compatible_urllib3"]
        for line in lines
    )
    score = (0.4 if has_requests else 0.0) + (0.6 if has_compatible_urllib3 else 0.0)
    details = {"has_requests_pin": has_requests, "has_compatible_urllib3": has_compatible_urllib3}
    if score == 1.0:
        return VerifyResult(True, 1.0, "dependency conflict repaired", details)
    return VerifyResult(False, 0.0, "urllib3 remains incompatible with requests", details)


def seed_chmod(root: Path) -> None:
    write(root / "home" / "agent" / ".ssh" / "id_rsa", "PRIVATE KEY\n")
    write(root / "home" / "agent" / ".ssh" / "config", "Host *\n  StrictHostKeyChecking no\n")
    set_expected_mode(root, root / "home" / "agent" / ".ssh", 0o777)
    set_expected_mode(root, root / "home" / "agent" / ".ssh" / "id_rsa", 0o777)
    set_expected_mode(root, root / "home" / "agent" / ".ssh" / "config", 0o777)
    create_host_oracle(
        root,
        {
            "required_modes": {
                "home/agent/.ssh": 0o700,
                "home/agent/.ssh/id_rsa": 0o600,
                "home/agent/.ssh/config": 0o600,
            }
        },
    )


def verify_chmod(root: Path) -> VerifyResult:
    if tamper := require_no_tamper(root):
        return tamper
    oracle, oracle_error = verify_host_oracle(root)
    if oracle_error:
        return oracle_error
    ssh_dir = root / "home" / "agent" / ".ssh"
    private_key = ssh_dir / "id_rsa"
    config = ssh_dir / "config"
    for path in [ssh_dir, private_key, config]:
        if not path.exists():
            return VerifyResult(False, 0.0, f"{path.relative_to(root)} missing")
    modes = {
        "dir": read_expected_mode(root, ssh_dir),
        "key": read_expected_mode(root, private_key),
        "config": read_expected_mode(root, config),
    }
    expected = oracle["required_modes"]
    expected_by_label = {
        "dir": expected["home/agent/.ssh"],
        "key": expected["home/agent/.ssh/id_rsa"],
        "config": expected["home/agent/.ssh/config"],
    }
    checks = {label: modes[label] == expected_by_label[label] for label in modes}
    score = sum(checks.values()) / len(checks)
    if score == 1.0:
        return VerifyResult(True, 1.0, "ssh permissions locked down", {"modes": modes})
    return VerifyResult(False, 0.0, "insecure modes remain", {"modes": modes, "expected": expected_by_label})


def partial_nginx(root: Path) -> None:
    write(root / "etc" / "nginx" / "nginx.conf", "events {}\nhttp { server { listen 8080; } }\n")


def partial_pytest(root: Path) -> None:
    write(root / "src" / "utils.py", "def nth_item(items, n):\n    return items[n - 1]\n\ndef middle(items):\n    return items[0]\n")


def partial_logs(root: Path) -> None:
    write(root / "output" / "summary.json", json.dumps({"total_errors": 3}))


def partial_db(root: Path) -> None:
    write(root / "migrations" / "001_create_schema.sql", "CREATE TABLE orders(id INTEGER PRIMARY KEY);\n")


def partial_deps(root: Path) -> None:
    write(root / "requirements.txt", "requests==2.31.0\n")


def partial_chmod(root: Path) -> None:
    set_expected_mode(root, root / "home" / "agent" / ".ssh", 0o700)
    set_expected_mode(root, root / "home" / "agent" / ".ssh" / "id_rsa", 0o600)


TASKS: dict[str, TaskSpec] = {
    "task_1_nginx_fix": TaskSpec(
        "task_1_nginx_fix",
        "Fix broken Nginx reverse proxy configuration",
        "devops",
        "medium",
        "Repair /etc/nginx/nginx.conf so /api/ proxies to app_backend and nginx syntax is valid.",
        seed_nginx,
        verify_nginx,
        lambda root: ["python -c \"from pathlib import Path; p=Path('etc/nginx/nginx.conf'); s=p.read_text(); p.write_text(s.replace('proxy_pass http://app_backend\\n', 'proxy_pass http://app_backend;\\n'))\""],
        partial_nginx,
    ),
    "task_2_pytest_repair": TaskSpec(
        "task_2_pytest_repair",
        "Repair failing pytest library tests",
        "software-engineering",
        "medium",
        "Fix src/utils.py so nth_item uses 1-based indexing while middle still returns the central item.",
        seed_pytest,
        verify_pytest,
        lambda root: ["python -c \"from pathlib import Path; Path('src/utils.py').write_text('def nth_item(items, n):\\n    return items[n - 1]\\n\\ndef middle(items):\\n    return items[len(items) // 2]\\n')\""],
        partial_pytest,
    ),
    "task_3_log_triage": TaskSpec(
        "task_3_log_triage",
        "Generate structured log error report",
        "observability",
        "medium",
        "Read /var/log/app.log and create /output/summary.json with total_errors and error_counts.",
        seed_logs,
        verify_logs,
        lambda root: ["python -c \"import json, pathlib, collections; counts=collections.Counter(); [counts.update([line.split()[2]]) for line in pathlib.Path('var/log/app.log').read_text().splitlines() if ' ERROR ' in line]; pathlib.Path('output').mkdir(exist_ok=True); pathlib.Path('output/summary.json').write_text(json.dumps({'total_errors': sum(counts.values()), 'error_counts': dict(counts)}, sort_keys=True))\""],
        partial_logs,
    ),
    "task_4_db_migration": TaskSpec(
        "task_4_db_migration",
        "Repair SQLite migration ordering",
        "database",
        "hard",
        "Fix migrations/001_create_schema.sql so customers exists before orders and foreign keys enforce correctly.",
        seed_db,
        verify_db,
        lambda root: ["python -c \"from pathlib import Path; Path('migrations/001_create_schema.sql').write_text('PRAGMA foreign_keys = ON;\\nCREATE TABLE customers (\\n  id INTEGER PRIMARY KEY,\\n  email TEXT NOT NULL UNIQUE\\n);\\nCREATE TABLE orders (\\n  id INTEGER PRIMARY KEY,\\n  customer_id INTEGER NOT NULL,\\n  total_cents INTEGER NOT NULL,\\n  FOREIGN KEY (customer_id) REFERENCES customers(id)\\n);\\n')\""],
        partial_db,
    ),
    "task_5_dep_conflict": TaskSpec(
        "task_5_dep_conflict",
        "Resolve Python dependency conflict",
        "dependency-management",
        "medium",
        "Update requirements.txt so requests 2.31.0 has a compatible urllib3 dependency.",
        seed_deps,
        verify_deps,
        lambda root: ["python -c \"from pathlib import Path; Path('requirements.txt').write_text('requests==2.31.0\\nurllib3==2.0.7\\n')\""],
        partial_deps,
    ),
    "task_6_chmod_sec": TaskSpec(
        "task_6_chmod_sec",
        "Lock down SSH file permissions",
        "security",
        "medium",
        "Fix insecure 777 permissions under /home/agent/.ssh using 700 for the directory and 600 for files.",
        seed_chmod,
        verify_chmod,
        lambda root: ["python -c \"import json, os, pathlib; root=pathlib.Path('.'); paths={'home/agent/.ssh':448,'home/agent/.ssh/id_rsa':384,'home/agent/.ssh/config':384}; [os.chmod(p, m) for p,m in paths.items()]; pathlib.Path('.devbench_modes.json').write_text(json.dumps(paths, sort_keys=True))\""],
        partial_chmod,
    ),
}


def get_task(task_id: str) -> TaskSpec:
    return TASKS[task_id]


def seed_workspace(task_id: str, root: Path) -> TaskSpec:
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    spec = get_task(task_id)
    spec.seed(root)
    return spec

