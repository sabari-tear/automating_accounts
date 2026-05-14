"""Reel Caption Engine.

Uses an LLM to generate styled text overlays from a VideoContextAnalysis.
The output is a list of TextOverlay objects ready to pass to VideoTextEngine.

Usage::

    from library.llm_provider import LLM
    from library.video_context_analyzer import VideoContextAnalyzer
    from library.reel_caption_engine import ReelCaptionEngine
    from library.video_text_engine import VideoTextEngine

    llm = LLM(
        api_key="YOUR_KEY",
        model_name="gemini-2.5-flash-lite",
        system_prompt="You design punchy caption overlays for short video reels.",
    )

    analysis = VideoContextAnalyzer().analyze("clip.mp4")
    overlays = ReelCaptionEngine(llm=llm).generate(analysis)

    engine = VideoTextEngine(ffmpeg_path=..., ffprobe_path=...)
    engine.add_text_overlays("clip.mp4", overlays, output_path="out.mp4")
"""

from .engine import ReelCaptionEngine, CaptionOverlayResult

__all__ = [
    "ReelCaptionEngine",
    "CaptionOverlayResult",
]
