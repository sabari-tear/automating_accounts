from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal, Sequence

import ffmpeg


VerticalPosition = Literal["up", "center", "down"]
DurationMode = Literal["full", "half"]


@dataclass(slots=True)
class TextOverlay:
    text: str
    position: VerticalPosition = "center"
    start_time: float | None = None
    end_time: float | None = None
    duration_mode: DurationMode = "full"
    font_size: int = 48
    font_color: str = "white"
    box: bool = True
    box_color: str = "black@0.55"
    box_border_width: int = 20
    x: str = "(w-text_w)/2"


class VideoTextEngine:
    def __init__(self, ffmpeg_path: str | None = None, ffprobe_path: str | None = None) -> None:
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path

    def add_text(
        self,
        video_path: str | Path,
        text: str,
        output_path: str | Path | None = None,
        position: VerticalPosition = "center",
        duration_mode: DurationMode = "full",
        start_time: float | None = None,
        end_time: float | None = None,
        font_size: int = 48,
        font_color: str = "white",
        box: bool = True,
        box_color: str = "black@0.55",
        box_border_width: int = 20,
    ) -> Path:
        overlay = TextOverlay(
            text=text,
            position=position,
            start_time=start_time,
            end_time=end_time,
            duration_mode=duration_mode,
            font_size=font_size,
            font_color=font_color,
            box=box,
            box_color=box_color,
            box_border_width=box_border_width,
        )
        return self.add_text_overlays(video_path, [overlay], output_path=output_path)

    def add_text_overlays(
        self,
        video_path: str | Path,
        overlays: Sequence[TextOverlay] | Iterable[TextOverlay],
        output_path: str | Path | None = None,
    ) -> Path:
        source_path = Path(video_path)
        if not source_path.exists():
            raise FileNotFoundError(f"Video not found: {source_path}")

        overlay_list = list(overlays)
        if not overlay_list:
            raise ValueError("At least one text overlay is required")

        destination_path = Path(output_path) if output_path else self._build_output_path(source_path)
        metadata = self._probe_video(source_path)
        duration = float(metadata["format"]["duration"])
        has_audio = any(stream.get("codec_type") == "audio" for stream in metadata.get("streams", []))

        stream = ffmpeg.input(str(source_path))
        video_stream = stream.video

        for overlay in overlay_list:
            start, end = self._resolve_time_window(overlay, duration)
            video_stream = video_stream.drawtext(
                text=self._escape_text(overlay.text),
                x=overlay.x,
                y=self._resolve_y_expression(overlay.position),
                fontsize=overlay.font_size,
                fontcolor=overlay.font_color,
                box=1 if overlay.box else 0,
                boxcolor=overlay.box_color,
                boxborderw=overlay.box_border_width,
                enable=f"between(t,{self._format_time(start)},{self._format_time(end)})",
            )

        if has_audio:
            output = ffmpeg.output(
                video_stream,
                stream.audio,
                str(destination_path),
                vcodec="libx264",
                acodec="copy",
                movflags="+faststart",
            )
        else:
            output = ffmpeg.output(
                video_stream,
                str(destination_path),
                vcodec="libx264",
                movflags="+faststart",
            )

        output.overwrite_output().run(cmd=self.ffmpeg_path, capture_stdout=True, capture_stderr=True)
        return destination_path

    def create_overlay(
        self,
        text: str,
        position: VerticalPosition = "center",
        start_time: float | None = None,
        end_time: float | None = None,
        duration_mode: DurationMode = "full",
        font_size: int = 48,
        font_color: str = "white",
        box: bool = True,
        box_color: str = "black@0.55",
        box_border_width: int = 20,
    ) -> TextOverlay:
        return TextOverlay(
            text=text,
            position=position,
            start_time=start_time,
            end_time=end_time,
            duration_mode=duration_mode,
            font_size=font_size,
            font_color=font_color,
            box=box,
            box_color=box_color,
            box_border_width=box_border_width,
        )

    def _probe_video(self, video_path: Path) -> dict:
        return ffmpeg.probe(str(video_path), cmd=self.ffprobe_path)

    def _resolve_time_window(self, overlay: TextOverlay, video_duration: float) -> tuple[float, float]:
        default_end = video_duration if overlay.duration_mode == "full" else video_duration / 2
        start = 0.0 if overlay.start_time is None else float(overlay.start_time)
        end = default_end if overlay.end_time is None else float(overlay.end_time)

        if start < 0:
            raise ValueError("start_time must be 0 or greater")
        if end <= start:
            raise ValueError("end_time must be greater than start_time")
        if start > video_duration:
            raise ValueError("start_time cannot exceed video duration")

        return start, min(end, video_duration)

    def _build_output_path(self, source_path: Path) -> Path:
        return source_path.with_name(f"{source_path.stem}_with_text{source_path.suffix}")

    def _resolve_y_expression(self, position: VerticalPosition) -> str:
        mapping = {
            "up": "h*0.15",
            "center": "(h-text_h)/2",
            "down": "h-text_h-h*0.15",
        }
        return mapping[position]

    def _escape_text(self, value: str) -> str:
        escaped = value.replace("\\", r"\\")
        escaped = escaped.replace(":", r"\:")
        escaped = escaped.replace("'", r"\'")
        escaped = escaped.replace("%", r"\%")
        return escaped

    def _format_time(self, value: float) -> str:
        return f"{value:.3f}".rstrip("0").rstrip(".")

def main() -> None:
    engine = VideoTextEngine()

    intro = engine.create_overlay(
        text="Welcome to the video",
        position="up",
        start_time=0,
        end_time=5,
    )
    highlight = engine.create_overlay(
        text="Important moment",
        position="down",
        start_time=8,
        end_time=14,
    )

    engine.add_text_overlays(
        video_path="input.mp4",
        overlays=[intro, highlight],
        output_path="output_with_text.mp4",
    )


if __name__ == "__main__":
    main()