import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 2:
        print(json.dumps({"error": "usage: feature_labeler_runtime_worker.py <text>"}))
        return 2

    worker_dir = Path(__file__).resolve().parent
    if str(worker_dir) not in sys.path:
        sys.path.insert(0, str(worker_dir))

    from step import _classify_ticket, _load_feature_labeler, _mock_labels  # noqa: E402

    text = " ".join(sys.argv[1:]).strip()
    classifier = _load_feature_labeler()
    if classifier is None:
        labels = _mock_labels(text)
        source = "mock"
    else:
        try:
            labels = _classify_ticket(classifier, text)
            source = "nli"
        except Exception:
            labels = _mock_labels(text)
            source = "mock"
    payload = {
        "issue_severity": str(labels.get("issue_severity") or "medium").lower(),
        "issue_urgency": str(labels.get("issue_urgency") or "medium").lower(),
        "business_impact": str(labels.get("business_impact") or "medium").lower(),
        "safety_concern": bool(labels.get("safety_concern")),
        "feature_labels_source": source,
    }
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
