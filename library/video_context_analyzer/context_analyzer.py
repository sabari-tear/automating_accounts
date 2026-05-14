"""Video Context Analyzer Engine.

Analyzes video frames using LLM to extract structured context.
Does NOT generate text or render parameters - analysis only.

Architecture:
- Frame Extraction: Decoupled from analysis (strategy pattern)
- LLM Analysis: Dependency-injected provider (injection pattern)
- Validation: Strict schema validation with custom exceptions
- Error Handling: Comprehensive error types for different failure modes
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import ffmpeg

from library.llm_provider import (
    ANALYSIS_PROMPT_TEMPLATE,
    HOOK_STYLES,
    INTENSITIES,
    LLM,
    LLMProvider,
    MOODS,
    PACES,
    SCENE_TYPES,
    TIME_RANGES,
    create_llm_from_env,
)
from library.llm_provider.exceptions import LLMFrameAnalysisError

logger = logging.getLogger(__name__)


class VideoProbeError(Exception):
    """Raised when video probing fails."""
    pass


class FrameExtractionError(Exception):
    """Raised when frame extraction fails."""
    pass


class VideoAnalysisError(Exception):
    """Raised when video analysis fails."""
    pass


class ValidationError(Exception):
    """Raised when analysis validation fails."""
    pass




@dataclass(slots=True)
class VideoContextAnalysis:
    """Structured analysis result for a video."""
    
    summary: str
    mood: str
    scene_type: str
    intensity: str
    pace: str
    visual_style: list[str]
    emotion_tags: list[str]
    hook_style_suggestions: list[str]
    best_moment: dict
    quality_flags: dict
    confidence: float
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "summary": self.summary,
            "mood": self.mood,
            "scene_type": self.scene_type,
            "intensity": self.intensity,
            "pace": self.pace,
            "visual_style": self.visual_style,
            "emotion_tags": self.emotion_tags,
            "hook_style_suggestions": self.hook_style_suggestions,
            "best_moment": self.best_moment,
            "quality_flags": self.quality_flags,
            "confidence": self.confidence,
        }
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)


class FrameExtractor(ABC):
    """Abstract base for frame extraction strategies (strategy pattern)."""
    
    @abstractmethod
    def extract_frames(
        self,
        video_path: Path,
        duration: float,
        frames_per_second: int,
        max_frames: int,
    ) -> list[str]:
        """Extract frames from video as base64-encoded JPEG."""
        pass


class FFmpegFrameExtractor(FrameExtractor):
    """FFmpeg-based frame extraction strategy."""
    
    def __init__(self, ffmpeg_path: Optional[str] = None):
        self.ffmpeg_path = ffmpeg_path
        logger.debug(f"Initialized FFmpegFrameExtractor with path: {ffmpeg_path}")
    
    def extract_frames(
        self,
        video_path: Path,
        duration: float,
        frames_per_second: int,
        max_frames: int,
    ) -> list[str]:
        """Extract frames from video using FFmpeg."""
        import base64
        import tempfile
        
        frame_interval = frames_per_second
        frame_times = []
        
        # First 3 seconds
        for i in range(min(3, max_frames)):
            frame_times.append(i * frame_interval)
        
        # Last 3 seconds (if room available)
        if len(frame_times) < max_frames:
            remaining = max_frames - len(frame_times)
            for i in range(remaining):
                time_from_end = duration - ((remaining - i) * frame_interval)
                if time_from_end > 0 and time_from_end not in frame_times:
                    frame_times.append(time_from_end)
        
        frames_b64 = []
        for frame_time in frame_times:
            try:
                frame_b64 = self._extract_frame_at_time(video_path, frame_time)
                if frame_b64:
                    frames_b64.append(frame_b64)
            except Exception as e:
                logger.warning(f"Failed to extract frame at {frame_time}s: {e}")
                continue
        
        if not frames_b64:
            raise FrameExtractionError(f"Could not extract any frames from {video_path}")
        
        logger.debug(f"Extracted {len(frames_b64)} frames from {video_path}")
        return frames_b64
    
    def _extract_frame_at_time(self, video_path: Path, time_seconds: float) -> Optional[str]:
        """Extract single frame at given time as base64 JPEG (single-pass)."""
        import base64

        try:
            jpeg_bytes, _ = (
                ffmpeg
                .input(str(video_path), ss=time_seconds)
                .video
                .filter("scale", 512, -1)
                .output("pipe:", vframes=1, format="image2", vcodec="mjpeg")
                .run(capture_stdout=True, capture_stderr=True, cmd=self.ffmpeg_path)
            )
            if not jpeg_bytes:
                return None
            return base64.b64encode(jpeg_bytes).decode("utf-8")
        except Exception as e:
            raise FrameExtractionError(f"Frame extraction failed at {time_seconds}s: {e}")





class VideoContextAnalyzer:
    """Analyze video context using LLM with dependency injection."""
    
    def __init__(
        self,
        llm: Optional[LLM] = None,
        llm_provider: Optional[LLMProvider] = None,
        analysis_prompt_template: Optional[str] = None,
        frame_extractor: Optional[FrameExtractor] = None,
        ffmpeg_path: Optional[str] = None,
        ffprobe_path: Optional[str] = None,
    ):
        """
        Initialize analyzer with dependency injection.

        Args:
            llm: LLM instance (preferred). Created via LLM(api_key=..., model_name=..., system_prompt=...).
            llm_provider: Legacy LLMProvider instance. Ignored when `llm` is supplied.
            analysis_prompt_template: Optional prompt template override. If not set,
                VIDEO_CONTEXT_ANALYSIS_PROMPT_TEMPLATE env var is used, then default template.
            frame_extractor: FrameExtractor instance. If None, uses FFmpegFrameExtractor.
            ffmpeg_path: Path to ffmpeg binary (passed to frame extractor).
            ffprobe_path: Path to ffprobe binary.

        Example::

            from library.llm_provider import LLM
            from library.video_context_analyzer import VideoContextAnalyzer

            llm = LLM(
                api_key="YOUR_KEY",
                model_name="gemini-2.0-flash",
                system_prompt="You are an expert video analyst.",
            )
            analyzer = VideoContextAnalyzer(llm=llm)
            result = analyzer.analyze("clip.mp4")
        """
        # Ensure .env is loaded before reading any env vars
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except Exception:
            pass

        if llm is not None:
            self.llm_provider = llm
            logger.debug(f"Initialized VideoContextAnalyzer with LLM model: {llm.model_name}")
        elif llm_provider is not None:
            self.llm_provider = llm_provider
            logger.debug(
                f"Initialized VideoContextAnalyzer with provider: "
                f"{llm_provider.config.provider}/{llm_provider.config.model}"
            )
        else:
            self.llm_provider = create_llm_from_env()
            logger.debug("Initialized VideoContextAnalyzer with env-based LLM")

        self.analysis_prompt_template = (
            analysis_prompt_template
            or os.getenv("VIDEO_CONTEXT_ANALYSIS_PROMPT_TEMPLATE")
            or ANALYSIS_PROMPT_TEMPLATE
        )
        # Resolve binary paths: explicit arg > env var > None (uses PATH)
        resolved_ffmpeg = ffmpeg_path or os.getenv("FFMPEG_PATH") or None
        resolved_ffprobe = ffprobe_path or os.getenv("FFPROBE_PATH") or None
        self.frame_extractor = frame_extractor or FFmpegFrameExtractor(resolved_ffmpeg)
        self.ffprobe_path = resolved_ffprobe
    
    def analyze(
        self,
        video_path: str | Path,
        frames_per_second: int = 1,
        max_frames: int = 6,
    ) -> VideoContextAnalysis:
        """
        Analyze video context.
        
        Args:
            video_path: Path to video file.
            frames_per_second: Extract 1 frame per N seconds.
            max_frames: Maximum frames to extract (default 6: 3 from start, 3 from end).
            
        Returns:
            VideoContextAnalysis object with structured context data.
            
        Raises:
            FileNotFoundError: If video not found
            VideoAnalysisError: If analysis fails
            ValidationError: If response validation fails
        """
        source_path = Path(video_path)
        if not source_path.exists():
            raise FileNotFoundError(f"Video not found: {source_path}")
        
        logger.info(f"Analyzing video: {source_path}")
        
        try:
            # Get video metadata
            metadata = self._probe_video(source_path)
            duration = float(metadata["format"]["duration"])
            logger.debug(f"Video duration: {duration}s")
            
            # Extract frames
            frames_b64 = self.frame_extractor.extract_frames(
                source_path,
                duration,
                frames_per_second,
                max_frames,
            )
            
            # Build prompt
            prompt = self.analysis_prompt_template.format(frame_count=len(frames_b64))
            
            # Analyze with LLM
            logger.debug(f"Sending {len(frames_b64)} frames to LLM")
            llm_response = self.llm_provider.analyze_frames(frames_b64, prompt)
            
            # Parse and validate response
            analysis = self._parse_and_validate(llm_response)
            
            logger.info(f"Analysis complete: mood={analysis.mood}, confidence={analysis.confidence:.1%}")
            return analysis
        except (FileNotFoundError, FrameExtractionError, LLMFrameAnalysisError):
            raise
        except Exception as e:
            raise VideoAnalysisError(f"Video analysis failed: {e}") from e
    
    def _probe_video(self, video_path: Path) -> dict:
        """Get video metadata."""
        try:
            kwargs = {}
            if self.ffprobe_path:
                kwargs["cmd"] = self.ffprobe_path
            return ffmpeg.probe(str(video_path), **kwargs)
        except Exception as e:
            raise VideoProbeError(f"Failed to probe video: {e}")
    
    def _parse_and_validate(self, llm_response: str) -> VideoContextAnalysis:
        """Parse and validate LLM response."""
        # Strip markdown code fences that some models wrap around JSON
        text = llm_response.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            # Drop first line (```json or ```) and last line (```)
            text = "\n".join(lines[1:-1]).strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValidationError(f"LLM response is not valid JSON: {e}")
        
        # Validate required fields
        required_fields = [
            "summary", "mood", "scene_type", "intensity", "pace",
            "visual_style", "emotion_tags", "hook_style_suggestions",
            "best_moment", "quality_flags", "confidence",
        ]
        
        for field in required_fields:
            if field not in data:
                raise ValidationError(f"Missing required field: {field}")
        
        # Validate enum fields
        if data["mood"] not in MOODS:
            raise ValidationError(f"Invalid mood: {data['mood']}")
        if data["scene_type"] not in SCENE_TYPES:
            raise ValidationError(f"Invalid scene_type: {data['scene_type']}")
        if data["intensity"] not in INTENSITIES:
            raise ValidationError(f"Invalid intensity: {data['intensity']}")
        if data["pace"] not in PACES:
            raise ValidationError(f"Invalid pace: {data['pace']}")
        
        # Validate best_moment
        if data["best_moment"]["time_range"] not in TIME_RANGES:
            raise ValidationError(f"Invalid time_range: {data['best_moment']['time_range']}")
        
        # Validate hook_style_suggestions — filter unknown values with a warning
        raw_hooks = data.get("hook_style_suggestions", [])
        valid_hooks = []
        for style in raw_hooks:
            if style in HOOK_STYLES:
                valid_hooks.append(style)
            else:
                logger.warning(f"Ignoring unknown hook_style '{style}' (not in allowed list)")
        data["hook_style_suggestions"] = valid_hooks or ["generic"]
        
        # Validate confidence
        if not 0.0 <= data["confidence"] <= 1.0:
            raise ValidationError(f"Confidence must be 0.0-1.0, got {data['confidence']}")
        
        logger.debug("Validation passed")
        
        return VideoContextAnalysis(
            summary=data["summary"],
            mood=data["mood"],
            scene_type=data["scene_type"],
            intensity=data["intensity"],
            pace=data["pace"],
            visual_style=data["visual_style"],
            emotion_tags=data["emotion_tags"],
            hook_style_suggestions=data["hook_style_suggestions"],
            best_moment=data["best_moment"],
            quality_flags=data["quality_flags"],
            confidence=data["confidence"],
        )


