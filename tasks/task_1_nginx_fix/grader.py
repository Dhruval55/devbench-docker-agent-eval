from pathlib import Path
from evaluation.task_specs import verify_nginx


if __name__ == "__main__":
    result = verify_nginx(Path("."))
    print(result.message)
    raise SystemExit(0 if result.passed else 1)

