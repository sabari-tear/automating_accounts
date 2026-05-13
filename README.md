# Pexels Video Compiler

Create video compilations from Pexels videos automatically.

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure API key:**
   - Copy `.env.example` to `.env`
   - Add your Pexels API key to `.env`
   ```
   PEXELS_API_KEY=your_key_here
   ```

## Usage

Edit `pexels_compiler.py` main() function to specify:
- Search query (e.g., "nature", "city", "ocean")
- Number of videos to download
- Output filename

```python
compiler.compile_from_search("nature", num_videos=5, output_filename="my_compilation.mp4")
```

Then run:
```bash
python pexels_compiler.py
```

## Gemini Veo Video Generation

1. Add your Gemini API key to `.env`:
   ```
   GEMINI_API_KEY=your_key_here
   ```

2. Generate a video from a prompt:
   ```bash
   python gemini_veo_generator.py --prompt "A cinematic drone shot over snowy mountains at sunrise" --output veo_output.mp4
   ```

3. Optional flags:
   - `--model` (default: `veo-2.0-generate-001`)
   - `--aspect-ratio` (`16:9`, `9:16`, `1:1`)
   - `--duration` polling timeout seconds (default: `900`)

## FFmpeg Text Overlay Engine

Use `video_text_engine.py` to place timed text on top of a video with FFmpeg.

Requirements:
- Install Python dependencies from `requirements.txt`
- Install the FFmpeg binaries and make sure `ffmpeg` and `ffprobe` are available on your PATH

Simple usage:

```python
from video_text_engine import VideoTextEngine

engine = VideoTextEngine()
engine.add_text(
   video_path="input.mp4",
   text="Hello world",
   output_path="output.mp4",
   position="center",
   duration_mode="half",
)
```

Multiple timed overlays:

```python
from video_text_engine import VideoTextEngine

engine = VideoTextEngine()
overlays = [
   engine.create_overlay("Intro text", position="up", start_time=0, end_time=4),
   engine.create_overlay("Center callout", position="center", start_time=5, end_time=9),
   engine.create_overlay("Closing text", position="down", start_time=10, end_time=14),
]

engine.add_text_overlays("input.mp4", overlays, output_path="timed_output.mp4")
```

Supported overlay controls:
- `position`: `up`, `center`, `down`
- `duration_mode`: `full` or `half`
- `start_time` and `end_time` to control exact time windows
- Additional styling options like `font_size`, `font_color`, and background box settings

## Features

- Search Pexels videos by keyword
- Automatically download videos
- Combine multiple videos into one compilation
- Overlay timed text on existing videos with FFmpeg
- Customizable output filename

## Files

- `downloads/` - Downloaded videos saved here
- `*.mp4` - Compiled video output files
