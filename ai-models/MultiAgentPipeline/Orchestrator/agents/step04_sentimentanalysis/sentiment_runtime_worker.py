import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 3:
        print(json.dumps({"error": "usage: sentiment_runtime_worker.py <model_dir> <text>"}))
        return 2

    model_dir = sys.argv[1]
    text = " ".join(sys.argv[2:]).strip()
    if not text:
        print(json.dumps({"text_sentiment": 0.0, "processing_time_ms": 0.0}))
        return 0

    runtime_src = Path("/app/sentiment_pipeline")
    if str(runtime_src) not in sys.path:
        sys.path.insert(0, str(runtime_src))

    from inference import SentimentPredictor  # noqa: E402

    predictor = SentimentPredictor(model_dir=model_dir, device="cpu")
    result = predictor.predict(text)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
