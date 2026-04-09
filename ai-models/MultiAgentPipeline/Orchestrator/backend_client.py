from __future__ import annotations

import os


_INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "").strip()


def internal_backend_headers() -> dict[str, str]:
    if not _INTERNAL_API_KEY:
        return {}
    return {"X-Internal-Key": _INTERNAL_API_KEY}
