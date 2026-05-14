#!/usr/bin/env python3
"""
Main: Analyze video context using best-practice libraries.

Demonstrates:
1. Dependency injection for LLM providers
2. Error handling with custom exceptions
3. Structured configuration management
4. Extensible architecture (easy to add new providers/extractors)
"""

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from library.llm_provider import (
    LLM,
    LLMConfig,
    create_llm_from_env,
    create_provider,
    list_available_providers,
)
from library.video_context_analyzer import (
    VideoContextAnalyzer,
    VideoAnalysisError,
    ValidationError,
)
from library.reel_caption_engine import ReelCaptionEngine
from library.video_text_engine.engine import VideoTextEngine
from library.instagram_post_engine import InstagramPostEngine
import ffmpeg as _ffmpeg

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)


def _validate_instagram_format(probe_data: dict, duration: float) -> None:
    """Warn if video doesn't meet Instagram Reels requirements."""
    video_stream = next(
        (s for s in probe_data.get("streams", []) if s.get("codec_type") == "video"), None
    )
    if video_stream:
        w = int(video_stream.get("width", 0))
        h = int(video_stream.get("height", 0))
        if w > 0 and h > 0:
            ratio = w / h
            if not (0.50 <= ratio <= 0.60):  # 9:16 = 0.5625
                print(f"\n⚠️  Format: {w}x{h} (ratio {ratio:.2f}) — Instagram Reels expects 9:16 (1080x1920)")
    if duration < 3:
        print(f"\n⚠️  Duration {duration:.1f}s — Instagram Reels minimum is 3 seconds")
    elif duration > 90:
        print(f"\n⚠️  Duration {duration:.1f}s — Instagram Reels maximum is 90 seconds")


def _get_best_moment_time(analysis, duration: float) -> float:
    """Convert best_moment time_range to a concrete timestamp."""
    time_range = (analysis.best_moment or {}).get("time_range", "unclear")
    if time_range == "first_3_seconds":
        return 1.5
    elif time_range == "last_3_seconds":
        return max(0.0, duration - 2.0)
    elif time_range == "both":
        return 1.5
    else:
        return duration / 2


def _extract_thumbnail(video_path: str | Path, time_seconds: float, output_path: str | Path) -> None:
    """Extract a single frame from video at the given time and save as JPEG."""
    (
        _ffmpeg
        .input(str(video_path), ss=time_seconds)
        .video
        .filter("scale", 1080, -1)
        .output(str(output_path), vframes=1, format="image2", vcodec="mjpeg")
        .overwrite_output()
        .run(
            capture_stdout=True,
            capture_stderr=True,
            cmd=os.getenv("FFMPEG_PATH") or "ffmpeg",
        )
    )


def analyze_video_default(video_path: str | Path) -> None:
    """Analyze video using env-driven LLM defaults (model/prompt from .env)."""
    print(f"\n📹 Analyzing video: {video_path}")
    print("-" * 60)

    try:
        # ── Step 1: context analysis ──────────────────────────────────────
        analysis_llm = create_llm_from_env()
        analyzer = VideoContextAnalyzer(llm=analysis_llm)

        print("🔍 Extracting frames...")
        print("📊 Analyzing with env-configured LLM...")

        analysis = analyzer.analyze(
            video_path=video_path,
            frames_per_second=1,
            max_frames=6,
        )

        print("\n✅ Analysis Complete")
        print(f"   mood={analysis.mood}  scene={analysis.scene_type}  "
              f"intensity={analysis.intensity}  pace={analysis.pace}  "
              f"confidence={analysis.confidence:.0%}")

        # ── Step 2: generate caption overlays ────────────────────────────
        # No system_prompt override — let ReelCaptionEngine use its own cinematic prompt.
        # High temperature (1.0) for creative, non-cliché output.
        caption_llm = LLM(
            api_key=analysis_llm._provider.config.get_api_key(),
            model_name=analysis_llm.model_name,
            temperature=1.0,
        )
        caption_engine = ReelCaptionEngine(llm=caption_llm, overlay_count=1)

        print("\n✍️  Generating caption overlays...")
        probe_data = _ffmpeg.probe(
            str(video_path),
            cmd=os.getenv("FFPROBE_PATH") or "ffprobe",
        )
        duration = float(probe_data["format"]["duration"])
        _validate_instagram_format(probe_data, duration)

        result = caption_engine.generate(analysis, video_duration=duration)
        for i, o in enumerate(result.overlays, 1):
            print(f"   [{i}] \"{o.text}\"  pos={o.position}  "
                  f"{o.start_time:.1f}s–{o.end_time:.1f}s  "
                  f"size={o.font_size}  color={o.font_color}")

        # ── Step 3: render ────────────────────────────────────────────────
        output_path = Path(video_path).stem + "_captioned.mp4"
        engine = VideoTextEngine(
            ffmpeg_path=os.getenv("FFMPEG_PATH"),
            ffprobe_path=os.getenv("FFPROBE_PATH"),
        )

        print(f"\n🎬 Rendering → {output_path}")
        engine.add_text_overlays(video_path, result.overlays, output_path=output_path)
        print(f"✅ Done: {output_path}")

        # ── Step 4: extract thumbnail ─────────────────────────────────────
        thumb_time = _get_best_moment_time(analysis, duration)
        thumb_path = Path(video_path).stem + "_thumbnail.jpg"
        print(f"\n🖼️  Extracting thumbnail at {thumb_time:.1f}s → {thumb_path}")
        _extract_thumbnail(video_path, thumb_time, thumb_path)
        print(f"✅ Thumbnail saved: {thumb_path}")

        # ── Step 5: Instagram post ────────────────────────────────────────
        print("\n📱 Generating Instagram post...")
        post_engine = InstagramPostEngine(llm=caption_llm)
        post = post_engine.generate(analysis)
        post_path = Path(video_path).stem + "_post.txt"
        post.save(post_path)
        print(f"✅ Post saved: {post_path}")
        print(f"   {post.preview()}")

        return analysis

    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    except (VideoAnalysisError, ValidationError) as e:
        print(f"❌ Analysis Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
        logger.exception("Full traceback:")
        sys.exit(1)


def analyze_video_custom_provider(video_path: str | Path, provider_name: str) -> None:
    """Analyze video using custom LLM provider."""
    print(f"\n📹 Analyzing with {provider_name} provider: {video_path}")
    print("-" * 60)
    
    try:
        # Create custom configuration
        config = LLMConfig(
            provider=provider_name,
            model="gemini-2.0-flash" if provider_name == "google" else "gpt-4-vision",
            temperature=0.3,
            max_tokens=2000,
        )
        
        # Create provider with custom config
        provider = create_provider(config)
        
        # Create analyzer with custom provider (dependency injection)
        analyzer = VideoContextAnalyzer(llm_provider=provider)
        
        print("🔍 Extracting frames...")
        print(f"📊 Analyzing with {provider_name}...")
        
        analysis = analyzer.analyze(video_path=video_path)
        
        print("\n✅ Analysis Complete")
        print("=" * 60)
        print(f"\n📄 Structured JSON Output:")
        print(analysis.to_json())
        
        return analysis
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


def save_analysis(analysis, output_path: str | Path) -> None:
    """Save analysis to JSON file."""
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, "w") as f:
        f.write(analysis.to_json())
    
    print(f"\n💾 Saved to: {output_file}")


def show_available_providers() -> None:
    """Display available LLM providers."""
    available = list_available_providers()
    print("\n📦 Available LLM Providers:")
    for provider in available:
        print(f"   • {provider}")


def main():
    """Main entry point."""
    # Example video path
    video_path = "test/sample_input_videos/2888111587029525988_47150597545.mp4"
    
    # Check if video exists
    if not Path(video_path).exists():
        print(f"❌ Video not found: {video_path}")
        print("\n💡 Usage:")
        print(f"   python main.py                         # Analyze with default provider")
        print(f"   python main.py <video_path>            # Analyze specific video")
        print(f"   python main.py <video_path> <provider> # Use custom provider")
        show_available_providers()
        sys.exit(1)
    
    # Analyze with default provider
    analysis = analyze_video_default(video_path)
    
    # Save to file
    save_analysis(analysis, "analysis_output.json")
    
    print("\n" + "=" * 60)
    print("✨ Done!")


if __name__ == "__main__":
    main()

