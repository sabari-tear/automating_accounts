"""Video Context Analyzer Library.

Analyzes video frames using LLM to extract structured context.
Does NOT generate text or render parameters - analysis only.

Features:
- Dependency injection for LLM providers
- Pluggable frame extraction strategies
- Comprehensive error handling with custom exceptions
- Strict schema validation
- Structured JSON output

Usage:
    from library.video_context_analyzer import VideoContextAnalyzer, VideoContextAnalysis
    
    analyzer = VideoContextAnalyzer()
    result = analyzer.analyze("path/to/video.mp4")
    print(result.to_json())

Custom Provider:
    from library.llm_provider import LLMConfig, create_provider
    from library.video_context_analyzer import VideoContextAnalyzer
    
    config = LLMConfig(provider="openai", model="gpt-4-vision")
    provider = create_provider(config)
    analyzer = VideoContextAnalyzer(llm_provider=provider)
    result = analyzer.analyze("path/to/video.mp4")
"""

from .context_analyzer import (
    FrameExtractor,
    FFmpegFrameExtractor,
    VideoContextAnalysis,
    VideoContextAnalyzer,
    VideoProbeError,
    FrameExtractionError,
    VideoAnalysisError,
    ValidationError,
)

__all__ = [
    # Main classes
    "VideoContextAnalyzer",
    "VideoContextAnalysis",
    # Extensibility
    "FrameExtractor",
    "FFmpegFrameExtractor",
    # Exceptions
    "VideoProbeError",
    "FrameExtractionError",
    "VideoAnalysisError",
    "ValidationError",
]

