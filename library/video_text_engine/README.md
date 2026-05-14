# Video Text Engine

Python FFmpeg-based engine to place timed text overlays on videos.

## Purpose

This document is the complete human-readable reference for all current engine parameters and behavior.

Machine-readable contract is available in video_text_engine_io_spec.json.

## Files

- Engine implementation: video_text_engine.py
- Input/output contract: video_text_engine_io_spec.json
- Test runner: test_overlay_engine.py

## Requirements

1. Install Python dependencies:

pip install -r requirements.txt

2. Install FFmpeg binaries:

- ffmpeg
- ffprobe

If binaries are not in PATH, pass ffmpeg_path and ffprobe_path to the constructor.

## Supported Types

- VerticalPosition: up | center | down
- DurationMode: full | half

## Constructor Reference

Method: VideoTextEngine(ffmpeg_path=None, ffprobe_path=None)

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| ffmpeg_path | str or None | No | None | Absolute path to ffmpeg binary. If None, uses PATH. |
| ffprobe_path | str or None | No | None | Absolute path to ffprobe binary. If None, uses PATH. |

## TextOverlay Object Reference

This object is used by create_overlay and add_text_overlays.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| text | str | Yes | - | Text to draw. |
| position | VerticalPosition | No | center | Vertical preset placement. |
| start_time | float or None | No | None | Start time in seconds. None resolves to 0. |
| end_time | float or None | No | None | End time in seconds. None resolves via duration_mode. |
| duration_mode | DurationMode | No | full | Used when end_time is None. |
| font_size | int | No | 48 | Font size. Must be >= 1. |
| font_color | str | No | white | FFmpeg color string. |
| box | bool | No | True | Show background box behind text. |
| box_color | str | No | black@0.55 | Box color with alpha support. |
| box_border_width | int | No | 20 | Box border/padding width. Must be >= 0. |
| shadow_x | int | No | 0 | Horizontal shadow offset in pixels. |
| shadow_y | int | No | 0 | Vertical shadow offset in pixels. |
| shadow_color | str | No | black@0.5 | Shadow color with alpha support. |
| x | str | No | (w-text_w)/2 | FFmpeg expression for horizontal placement. |

## Method Reference

### 1) add_text

Single-overlay convenience method.

Signature:

add_text(video_path, text, output_path=None, position=center, duration_mode=full, start_time=None, end_time=None, font_size=48, font_color=white, box=True, box_color=black@0.55, box_border_width=20, shadow_x=0, shadow_y=0, shadow_color=black@0.5) -> Path

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| video_path | str or Path | Yes | - | Source video path. Must exist. |
| text | str | Yes | - | Text content to render. |
| output_path | str or Path or None | No | None | Output path. If None, auto-generates source_with_text.ext. |
| position | VerticalPosition | No | center | up, center, down |
| duration_mode | DurationMode | No | full | full or half when end_time is None |
| start_time | float or None | No | None | Start time in seconds. |
| end_time | float or None | No | None | End time in seconds. |
| font_size | int | No | 48 | Text size. |
| font_color | str | No | white | Text color. |
| box | bool | No | True | Enable/disable text box background. |
| box_color | str | No | black@0.55 | Background box color. |
| box_border_width | int | No | 20 | Box border width/padding. |
| shadow_x | int | No | 0 | Shadow X offset. |
| shadow_y | int | No | 0 | Shadow Y offset. |
| shadow_color | str | No | black@0.5 | Shadow color. |

Return:

- Path to written output video

### 2) create_overlay

Builds and returns one TextOverlay object.

Signature:

create_overlay(text, position=center, start_time=None, end_time=None, duration_mode=full, font_size=48, font_color=white, box=True, box_color=black@0.55, box_border_width=20, shadow_x=0, shadow_y=0, shadow_color=black@0.5) -> TextOverlay

Parameters are the same as TextOverlay except x is not exposed in this helper and keeps default x expression.

Return:

- TextOverlay instance

### 3) add_text_overlays

Applies multiple overlays in one render pass.

Signature:

add_text_overlays(video_path, overlays, output_path=None) -> Path

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| video_path | str or Path | Yes | - | Source video path. Must exist. |
| overlays | Sequence[TextOverlay] or Iterable[TextOverlay] | Yes | - | At least one overlay required. |
| output_path | str or Path or None | No | None | Output path. If None, auto-generates source_with_text.ext. |

Return:

- Path to written output video

## Timing Resolution Rules

- If start_time is None, effective start is 0
- If end_time is None and duration_mode is full, effective end is full video duration
- If end_time is None and duration_mode is half, effective end is half video duration
- end_time is clamped to video duration
- start_time must be >= 0
- end_time must be > start_time
- start_time cannot exceed video duration

## Position Mapping

- up => h*0.15
- center => (h-text_h)/2
- down => h-text_h-h*0.15
- default x => (w-text_w)/2

## Text Escaping

Before passing to FFmpeg drawtext, engine escapes:

- backslash
- colon
- single quote
- percent

## Output Encoding Behavior

- Video codec: libx264
- movflags: +faststart
- If input has audio:
- audio codec: aac
- bitrate: 192k
- sample rate: 48000
- channels: 2
- If input has no audio:
- output has no audio stream

## Error Reference

Common errors you should handle:

- FileNotFoundError: Video not found at video_path
- ValueError: At least one text overlay is required
- ValueError: start_time must be 0 or greater
- ValueError: end_time must be greater than start_time
- ValueError: start_time cannot exceed video duration
- ffmpeg.Error: FFmpeg/ffprobe failure, invalid filter values, or binary/path issues

## Minimal Usage Examples

Single text:

from video_text_engine import VideoTextEngine

engine = VideoTextEngine(
    ffmpeg_path="C:/Practice/ffmpeg/bin/ffmpeg.exe",
    ffprobe_path="C:/Practice/ffmpeg/bin/ffprobe.exe",
)

out_path = engine.add_text(
    video_path="test/sample_input_videos/2888111587029525988_47150597545.mp4",
    text="Hello reel",
    output_path="test/sample_output_videos/quick_start.mp4",
    position="center",
    duration_mode="half",
    start_time=0,
    end_time=5,
    font_size=56,
    font_color="white",
    box=False,
    shadow_x=3,
    shadow_y=3,
    shadow_color="black@0.7",
)

Multiple overlays:

overlay_1 = engine.create_overlay(
    text="Hook",
    position="up",
    start_time=0,
    end_time=2,
    font_size=58,
    font_color="white",
    box=False,
    shadow_x=4,
    shadow_y=4,
    shadow_color="black@0.75",
)

overlay_2 = engine.create_overlay(
    text="Main point",
    position="center",
    start_time=2,
    end_time=6,
    font_size=50,
    font_color="yellow",
    box=True,
    box_color="black@0.45",
    box_border_width=16,
)

overlay_3 = engine.create_overlay(
    text="Follow for more",
    position="down",
    start_time=6,
    end_time=9,
    font_size=54,
    font_color="white",
    box=False,
    shadow_x=3,
    shadow_y=3,
    shadow_color="black@0.8",
)

story_out = engine.add_text_overlays(
    video_path="test/sample_input_videos/2934571291159600221_47912705569.mp4",
    overlays=[overlay_1, overlay_2, overlay_3],
    output_path="test/sample_output_videos/storyboard.mp4",
)

## Testing

Run:

python test_overlay_engine.py

Outputs are generated in test/sample_output_videos.

## Troubleshooting

- FFmpeg not found:
- Install ffmpeg/ffprobe or pass explicit constructor paths
- No audible sound in app player:
- Validate file in VLC/Windows Media Player
- Check stream with ffprobe
- Invalid timing values:
- Ensure end_time > start_time and start_time >= 0
