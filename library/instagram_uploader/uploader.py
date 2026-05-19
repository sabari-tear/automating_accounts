"""Instagram Uploader — logs in and uploads Reels with caption and thumbnail.

Uses instagrapi (Instagram private API) to:
  - Log in (with session cache to avoid re-login on every run)
  - Upload a video as a Reel with caption and cover thumbnail
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class UploadResult:
    """Result of a single Reel upload."""
    username: str
    video_path: str
    media_id: str
    success: bool
    error: Optional[str] = None


class InstagramUploader:
    """
    Uploads Reels to Instagram using instagrapi.

    Sessions are cached per username to avoid re-login on every run.
    Session files are stored at: sessions/{username}.json

    Args:
        username: Instagram username.
        password: Instagram password.
        session_dir: Directory to store session cache files. Defaults to 'sessions/'.
    """

    def __init__(self, username: str, password: str, session_dir: str | Path = "sessions") -> None:
        try:
            from instagrapi import Client
        except ImportError as e:
            raise ImportError(
                "instagrapi is not installed. Run: pip install instagrapi"
            ) from e

        self.username = username
        self._password = password
        self._session_dir = Path(session_dir)
        self._session_dir.mkdir(parents=True, exist_ok=True)
        self._session_path = self._session_dir / f"{username}.json"
        self._client = Client()
        self._logged_in = False

    def login(self) -> None:
        """Log in to Instagram, using cached session if available."""
        if self._logged_in:
            return

        if self._session_path.exists():
            try:
                self._client.load_settings(str(self._session_path))
                self._client.login(self.username, self._password)
                self._client.dump_settings(str(self._session_path))
                self._logged_in = True
                logger.info(f"[{self.username}] Logged in via cached session")
                return
            except Exception as e:
                logger.warning(f"[{self.username}] Cached session failed ({e}), doing fresh login")
                self._session_path.unlink(missing_ok=True)

        self._client.login(self.username, self._password)
        self._client.dump_settings(str(self._session_path))
        self._logged_in = True
        logger.info(f"[{self.username}] Fresh login successful")

    def upload_reel(
        self,
        video_path: str | Path,
        caption: str,
        thumbnail_path: Optional[str | Path] = None,
    ) -> UploadResult:
        """
        Upload a video as an Instagram Reel.

        Args:
            video_path: Path to the rendered .mp4 file.
            caption: Full post caption text (caption + hashtags).
            thumbnail_path: Optional path to a JPEG cover image.

        Returns:
            UploadResult with media_id on success, error message on failure.
        """
        video_path = Path(video_path)
        if not video_path.exists():
            return UploadResult(
                username=self.username,
                video_path=str(video_path),
                media_id="",
                success=False,
                error=f"Video not found: {video_path}",
            )

        try:
            self.login()
            kwargs: dict = {"caption": caption}
            if thumbnail_path and Path(thumbnail_path).exists():
                kwargs["thumbnail"] = Path(thumbnail_path)

            logger.info(f"[{self.username}] Uploading reel: {video_path.name}")
            media = self._client.clip_upload(path=video_path, **kwargs)
            media_id = str(media.id)
            logger.info(f"[{self.username}] Upload complete — media_id={media_id}")
            return UploadResult(
                username=self.username,
                video_path=str(video_path),
                media_id=media_id,
                success=True,
            )
        except Exception as e:
            logger.error(f"[{self.username}] Upload failed: {e}")
            return UploadResult(
                username=self.username,
                video_path=str(video_path),
                media_id="",
                success=False,
                error=str(e),
            )
