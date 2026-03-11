import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 2:
        print(json.dumps({"error": "usage: router_runtime_worker.py <text>"}))
        return 2

    worker_dir = Path(__file__).resolve().parent
    if str(worker_dir) not in sys.path:
        sys.path.insert(0, str(worker_dir))

    from step import _predict_department_from_text  # noqa: E402

    text = " ".join(sys.argv[1:]).strip()
    labels, scores, source = _predict_department_from_text(text)
    print(json.dumps({"labels": labels, "scores": scores, "source": source}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
