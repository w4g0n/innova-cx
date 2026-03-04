"""Cloud/runtime preflight checks for feature engineering training pipeline."""

import importlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REQUIRED_PKGS = [
    "torch",
    "transformers",
    "tokenizers",
    "accelerate",
    "pandas",
    "numpy",
    "sklearn",
    "tqdm",
]


def check_python():
    major, minor = sys.version_info[:2]
    if major < 3 or (major == 3 and minor < 10):
        raise RuntimeError(f"Python 3.10+ required, found {major}.{minor}")
    return f"{major}.{minor}.{sys.version_info.micro}"


def check_disk(path: Path, min_gb: float = 20.0):
    usage = shutil.disk_usage(path)
    free_gb = usage.free / (1024 ** 3)
    ok = free_gb >= min_gb
    return ok, round(free_gb, 2)


def check_package_imports():
    missing = []
    versions = {}
    for pkg in REQUIRED_PKGS:
        try:
            mod = importlib.import_module(pkg)
            versions[pkg] = getattr(mod, "__version__", "unknown")
        except Exception:
            missing.append(pkg)
    return missing, versions


def check_hf_login():
    token_in_env = bool(os.getenv("HUGGINGFACE_HUB_TOKEN") or os.getenv("HF_TOKEN"))
    whoami_ok = False
    try:
        proc = subprocess.run(
            ["huggingface-cli", "whoami"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        whoami_ok = proc.returncode == 0
    except Exception:
        whoami_ok = False
    return token_in_env or whoami_ok


def main():
    root = Path(__file__).resolve().parent
    required_dirs = ["Input", "output", "test", "logs", "models"]

    result = {
        "python": check_python(),
        "cwd": str(root),
        "dirs_ok": {},
        "disk": {},
        "packages": {},
        "hf_auth_ok": False,
    }

    for d in required_dirs:
        exists = (root / d).exists()
        result["dirs_ok"][d] = exists
        if not exists:
            raise RuntimeError(f"Required directory missing: {d}")

    disk_ok, free_gb = check_disk(root)
    result["disk"] = {"free_gb": free_gb, "min_gb": 20.0, "ok": disk_ok}
    if not disk_ok:
        raise RuntimeError(f"Insufficient free disk. Need >=20GB, found {free_gb}GB")

    missing, versions = check_package_imports()
    result["packages"] = versions
    if missing:
        raise RuntimeError(f"Missing Python packages: {missing}")

    result["hf_auth_ok"] = check_hf_login()
    if not result["hf_auth_ok"]:
        print(
            "[INFO] HuggingFace auth not detected. This is fine if your runtime "
            "can pull Phi-4 anonymously (as in your phase-2 setup)."
        )

    (root / "output" / "preflight_report.json").write_text(json.dumps(result, indent=2))
    print("Preflight checks passed")
    print(f"Saved report: {root / 'output' / 'preflight_report.json'}")


if __name__ == "__main__":
    main()
