#!/usr/bin/env python3
"""
Main: Automated Reel Creator with Instagram batch upload.

Modes:
  python main.py                        # process single test video (dev mode)
  python main.py --accounts accounts.json  # batch mode — reads accounts, uploads 2 reels per account
"""

import json
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
from library.instagram_uploader import InstagramUploader
from library.upload_log import pick_pending_videos, mark_uploaded
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


def process_and_upload_video(
    video_path: Path,
    uploader: InstagramUploader,
    extra_tags: list[str],
    output_dir: Path,
) -> bool:
    """
    Full pipeline for one video: analyze → caption → render → thumbnail → post → upload.

    Returns True on successful upload, False otherwise.
    """
    print(f"\n  📹 Processing: {video_path.name}")

    try:
        analysis_llm = create_llm_from_env()
        analyzer = VideoContextAnalyzer(llm=analysis_llm)
        analysis = analyzer.analyze(video_path=video_path, frames_per_second=1, max_frames=6)
        print(f"     mood={analysis.mood}  intensity={analysis.intensity}  confidence={analysis.confidence:.0%}")

        caption_llm = LLM(
            api_key=analysis_llm._provider.config.get_api_key(),
            model_name=analysis_llm.model_name,
            temperature=1.0,
        )

        # ── caption overlay ──
        caption_engine = ReelCaptionEngine(llm=caption_llm, overlay_count=1)
        probe_data = _ffmpeg.probe(str(video_path), cmd=os.getenv("FFPROBE_PATH") or "ffprobe")
        duration = float(probe_data["format"]["duration"])
        _validate_instagram_format(probe_data, duration)

        result = caption_engine.generate(analysis, video_duration=duration)
        caption_text = result.overlays[0].text if result.overlays else ""
        print(f"     caption: \"{caption_text}\"")

        # ── render ──
        output_dir.mkdir(parents=True, exist_ok=True)
        captioned_path = output_dir / (video_path.stem + "_captioned.mp4")
        engine = VideoTextEngine(
            ffmpeg_path=os.getenv("FFMPEG_PATH"),
            ffprobe_path=os.getenv("FFPROBE_PATH"),
        )
        engine.add_text_overlays(video_path, result.overlays, output_path=captioned_path)
        print(f"     rendered → {captioned_path.name}")

        # ── thumbnail ──
        thumb_time = _get_best_moment_time(analysis, duration)
        thumb_path = output_dir / (video_path.stem + "_thumbnail.jpg")
        _extract_thumbnail(video_path, thumb_time, thumb_path)
        print(f"     thumbnail → {thumb_path.name}")

        # ── Instagram post text ──
        post_engine = InstagramPostEngine(llm=caption_llm)
        post = post_engine.generate(analysis)

        # Inject account-specific extra tags into the post text
        if extra_tags:
            extra_block = " ".join(f"#{t.lstrip('#')}" for t in extra_tags)
            post_text = post.post_text + " " + extra_block
        else:
            post_text = post.post_text

        # Save post text
        post_path = output_dir / (video_path.stem + "_post.txt")
        post_path.write_text(post_text, encoding="utf-8")
        print(f"     post saved → {post_path.name}")

        # ── upload ──
        print(f"     uploading to @{uploader.username}...")
        upload_result = uploader.upload_reel(
            video_path=captioned_path,
            caption=post_text,
            thumbnail_path=thumb_path,
        )

        if upload_result.success:
            print(f"     ✅ Uploaded! media_id={upload_result.media_id}")
            return True
        else:
            print(f"     ❌ Upload failed: {upload_result.error}")
            return False

    except Exception as e:
        print(f"     ❌ Error processing {video_path.name}: {e}")
        logger.exception("Full traceback:")
        return False


def run_batch(accounts_path: str | Path) -> None:
    """
    Batch mode: read accounts.json, process and upload 2 reels per account.

    accounts.json schema:
    [
      {
        "username": "ig_username",
        "password": "ig_password",
        "folder": "reels/action",
        "description_style": "anime",
        "extra_tags": ["naruto", "animeedit"]
      }
    ]
    """
    accounts_file = Path(accounts_path)
    if not accounts_file.exists():
        print(f"❌ accounts file not found: {accounts_file}")
        sys.exit(1)

    try:
        accounts = json.loads(accounts_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in {accounts_file}: {e}")
        sys.exit(1)

    if not isinstance(accounts, list) or not accounts:
        print("❌ accounts.json must be a non-empty JSON array")
        sys.exit(1)

    print(f"\n📋 Loaded {len(accounts)} account(s) from {accounts_file}")
    print("=" * 60)

    total_uploaded = 0
    total_failed = 0

    for account in accounts:
        username = account.get("username", "").strip()
        password = account.get("password", "").strip()
        folder = account.get("folder", "").strip()
        extra_tags = account.get("extra_tags", [])

        if not username or not password or not folder:
            print(f"\n⚠️  Skipping incomplete account entry: {account}")
            continue

        print(f"\n👤 Account: @{username}  |  folder: {folder}")
        print("-" * 50)

        # Find 2 pending (not yet uploaded) videos
        videos = pick_pending_videos(username=username, folder=folder, count=2)
        if not videos:
            print(f"   ℹ️  No pending videos in {folder} — all already uploaded or folder is empty")
            continue

        print(f"   Found {len(videos)} pending video(s): {[v.name for v in videos]}")

        uploader = InstagramUploader(username=username, password=password)
        output_dir = Path(folder) / "output"

        for video_path in videos:
            success = process_and_upload_video(
                video_path=video_path,
                uploader=uploader,
                extra_tags=extra_tags,
                output_dir=output_dir,
            )
            if success:
                mark_uploaded(username=username, video_path=str(video_path))
                total_uploaded += 1
            else:
                total_failed += 1

    print("\n" + "=" * 60)
    print(f"✨ Batch complete — uploaded: {total_uploaded}  failed: {total_failed}")


def main():
    """Main entry point."""
    # ── Batch mode: python main.py --accounts accounts.json ──────────────
    if "--accounts" in sys.argv:
        idx = sys.argv.index("--accounts")
        if idx + 1 >= len(sys.argv):
            print("❌ --accounts requires a path argument, e.g. --accounts accounts.json")
            sys.exit(1)
        run_batch(sys.argv[idx + 1])
        return

    # ── Dev mode: single test video ───────────────────────────────────────
    video_path = "test/sample_input_videos/2888111587029525988_47150597545.mp4"

    if not Path(video_path).exists():
        print(f"❌ Video not found: {video_path}")
        print("\n💡 Usage:")
        print("   python main.py                           # dev mode (single video)")
        print("   python main.py --accounts accounts.json  # batch mode")
        show_available_providers()
        sys.exit(1)

    analysis = analyze_video_default(video_path)
    save_analysis(analysis, "analysis_output.json")

    print("\n" + "=" * 60)
    print("✨ Done!")


if __name__ == "__main__":
    main()

