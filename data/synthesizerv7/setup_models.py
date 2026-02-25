"""
Downloads and stores Synthesizer v7 models into local folders:
  - models/generator/phi-4
  - models/classifier/deberta-v3-base-mnli-fever-anli

Usage:
  python setup_models.py
  python setup_models.py --force
"""

import argparse
from pathlib import Path

from huggingface_hub import snapshot_download


BASE_DIR = Path(__file__).resolve().parent
GENERATOR_DIR = BASE_DIR / "models" / "generator" / "phi-4"
CLASSIFIER_DIR = BASE_DIR / "models" / "classifier" / "deberta-v3-base-mnli-fever-anli"


def _model_exists(target_dir: Path) -> bool:
    return (target_dir / "config.json").exists()


def download(repo_id: str, target_dir: Path, force: bool = False) -> None:
    if _model_exists(target_dir) and not force:
        print(f"Skipping {repo_id}: model already present at {target_dir}")
        return

    target_dir.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {repo_id} -> {target_dir}")
    snapshot_download(
        repo_id=repo_id,
        local_dir=str(target_dir),
        local_dir_use_symlinks=False,
        resume_download=True,
    )
    print(f"Done: {repo_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download local models for Synthesizer v7")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-download even if local model files already exist",
    )
    args = parser.parse_args()

    download("microsoft/phi-4", GENERATOR_DIR, force=args.force)
    download("MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli", CLASSIFIER_DIR, force=args.force)
    print("All models downloaded.")


if __name__ == "__main__":
    main()
