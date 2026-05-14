"""Video Text Engine Library.

FFmpeg-based text overlay rendering for videos with full control over position,
duration, timing, font size, colors, box styling, and shadows.
"""

from .engine import (
    TextOverlay,
    VideoTextEngine,
)

__all__ = [
    "VideoTextEngine",
    "TextOverlay",
]
