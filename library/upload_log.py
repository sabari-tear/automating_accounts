"""Upload log — tracks which videos have already been uploaded per account.

Stored in upload_log.json beside main.py.
Structure:
{
  "username_1": ["path/to/video1.mp4", "path/to/video2.mp4"],
  "username_2": [...]
}
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_LOG_PATH = Path("upload_log.json")


def load_log(log_path: Path = _DEFAULT_LOG_PATH) -> dict[str, list[str]]:
    """Load the upload log. Returns an empty dict if file doesn't exist."""
    if not log_path.exists():
        return {}
    try:
        return json.loads(log_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"Could not read upload log ({e}), starting fresh")
        return {}


def save_log(log: dict[str, list[str]], log_path: Path = _DEFAULT_LOG_PATH) -> None:
    """Persist the upload log to disk."""
    log_path.write_text(json.dumps(log, indent=2), encoding="utf-8")


def is_uploaded(username: str, video_path: str | Path, log_path: Path = _DEFAULT_LOG_PATH) -> bool:
    """Return True if this video has already been uploaded for this account."""
    log = load_log(log_path)
    return str(video_path) in log.get(username, [])


def mark_uploaded(username: str, video_path: str | Path, log_path: Path = _DEFAULT_LOG_PATH) -> None:
    """Record that a video has been uploaded for this account."""
    log = load_log(log_path)
    log.setdefault(username, [])
    entry = str(video_path)
    if entry not in log[username]:
        log[username].append(entry)
    save_log(log, log_path)


def pick_pending_videos(
    username: str,
    folder: str | Path,
    count: int = 2,
    log_path: Path = _DEFAULT_LOG_PATH,
) -> list[Path]:
    """
    Return up to `count` .mp4 files in `folder` not yet uploaded for `account`.
    Sorted by name for deterministic ordering.
    """
    folder = Path(folder)
    if not folder.exists():
        logger.warning(f"Folder not found: {folder}")
        return []

    log = load_log(log_path)
    uploaded = set(log.get(username, []))

    pending = sorted(
        [p for p in folder.glob("*.mp4") if str(p) not in uploaded],
        key=lambda p: p.name,
    )
    return pending[:count]
