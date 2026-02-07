"""Local session history — stores sessions on disk as JSON.

Every session result is saved locally regardless of whether it's
uploaded to the API.  This gives users a persistent record they own
and lets the CLI show progression even when offline.

Storage layout:
    ~/.squash_vision/
    ├── config.json          # user_id, API URL, preferences
    └── sessions/
        ├── 2024-01-15_143022.json
        ├── 2024-01-16_090511.json
        └── ...
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SQUASH_DIR = Path.home() / ".squash_vision"
SESSIONS_DIR = SQUASH_DIR / "sessions"
CONFIG_PATH = SQUASH_DIR / "config.json"


def _ensure_dirs() -> None:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Config (user identity + preferences)
# ---------------------------------------------------------------------------

def load_config() -> dict[str, Any]:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text())
    return {}


def save_config(config: dict[str, Any]) -> None:
    _ensure_dirs()
    CONFIG_PATH.write_text(json.dumps(config, indent=2))


def get_user_id() -> str | None:
    return load_config().get("user_id")


def get_api_url() -> str:
    return load_config().get("api_url", "http://localhost:8000")


# ---------------------------------------------------------------------------
# Session storage
# ---------------------------------------------------------------------------

def save_session(result_dict: dict[str, Any]) -> Path:
    """Save a session result dict to local history.

    Returns the path to the saved file.
    """
    _ensure_dirs()
    now = datetime.now(timezone.utc)
    filename = now.strftime("%Y-%m-%d_%H%M%S") + ".json"
    path = SESSIONS_DIR / filename
    result_dict["saved_at"] = now.isoformat()
    path.write_text(json.dumps(result_dict, indent=2, default=str))
    return path


def list_sessions(limit: int = 50) -> list[dict[str, Any]]:
    """Load recent sessions from local history, newest first."""
    _ensure_dirs()
    files = sorted(SESSIONS_DIR.glob("*.json"), reverse=True)[:limit]
    sessions = []
    for f in files:
        try:
            sessions.append(json.loads(f.read_text()))
        except (json.JSONDecodeError, OSError):
            continue
    return sessions


def get_local_stats() -> dict[str, Any]:
    """Compute stats from local session history."""
    sessions = list_sessions(limit=500)
    if not sessions:
        return {
            "total_sessions": 0,
            "total_drives": 0,
            "best_score": 0,
            "avg_score": 0,
            "recent_trend": [],
        }

    scores = [s.get("score", {}).get("total", 0) for s in sessions if s.get("score")]
    drives = sum(s.get("score", {}).get("num_shots", 0) for s in sessions)

    return {
        "total_sessions": len(sessions),
        "total_drives": drives,
        "best_score": round(max(scores) if scores else 0, 1),
        "avg_score": round(sum(scores) / len(scores) if scores else 0, 1),
        "recent_trend": [
            {
                "date": s.get("saved_at", "")[:10],
                "score": round(s.get("score", {}).get("total", 0), 1),
            }
            for s in sessions[:20]
        ],
    }
