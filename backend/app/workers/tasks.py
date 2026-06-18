from __future__ import annotations


def ping() -> str:
    return "pong"


def cleanup_stale_artifacts() -> dict[str, str]:
    return {"status": "noop"}
