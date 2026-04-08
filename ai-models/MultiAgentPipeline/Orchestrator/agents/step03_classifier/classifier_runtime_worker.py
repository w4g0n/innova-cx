import json
import sys
from pathlib import Path

# Must be imported before joblib unpickles the Pipeline so the class is
# resolvable in this module's namespace.
from feature_extractor import LinguisticFeatureExtractor  # noqa: F401


def main() -> int:
    if len(sys.argv) < 2:
        print(json.dumps({"error": "usage: classifier_runtime_worker.py <text>"}))
        return 2

    worker_dir = Path(__file__).resolve().parent
    if str(worker_dir) not in sys.path:
        sys.path.insert(0, str(worker_dir))

    from step import _heuristic_classify, _model_classify  # noqa: E402

    text = " ".join(sys.argv[1:]).strip()
    result = _model_classify(text)
    if result:
        label, confidence = result
        payload = {
            "label": label,
            "class_confidence": float(confidence),
            "classification_source": "model",
        }
    else:
        label, confidence = _heuristic_classify(text)
        payload = {
            "label": label,
            "class_confidence": float(confidence),
            "classification_source": "heuristic",
        }
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
