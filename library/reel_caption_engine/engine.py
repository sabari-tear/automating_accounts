"""Reel Caption Engine — core implementation.

Converts a VideoContextAnalysis into one or more TextOverlay objects
that can be passed directly to VideoTextEngine.add_text_overlays().
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

from library.llm_provider import LLM, create_llm_from_env
from library.video_context_analyzer import VideoContextAnalysis
from library.video_text_engine.engine import TextOverlay, VerticalPosition

logger = logging.getLogger(__name__)

# ── System prompt ──────────────────────────────────────────────────────────────

CAPTION_SYSTEM_PROMPT = """You are writing what a real anime edit viewer would type in the comment section on TikTok or Instagram Reels.

Imagine someone watching an anime edit and immediately typing their reaction — that's the caption.
It's not a label. It's not a description. It's a human reaction.

PERFECT examples — nail this tone exactly:
  "nah bro said enough 💀"
  "the way he didn't even flinch"
  "this scene broke me fr"
  "bro had ZERO chill"
  "nah they cooked with this one"
  "the music + this scene 😭"
  "bro said say less"
  "he did NOT have to go that hard"
  "this lives rent free"
  "they were NOT ready for him"
  "bro really said watch this"
  "the disrespect was crazy"
  "nah this was personal"
  "absolute cinema fr"
  "he carried the whole show"

NEVER write anything like:
  "unleash the beast" / "power overloaded" / "darkness awakens"
  "ultimate warrior" / "legendary battle" / "destiny calls"
  anything that sounds like a movie trailer or motivational poster
  anything formal, dramatic, or AI-generated sounding

RULES:
- Write as a viewer reacting, not a narrator describing
- Lowercase by default — caps only for emphasis on one word max (e.g. "bro had ZERO chill")
- Under 7 words
- One emoji max if it fits the mood naturally (💀 🔥 😭 🗿) — skip it if it feels forced
- Match the energy of the mood: hype = hype reaction, sad = sad reaction, betrayal = shocked reaction

TECHNICAL RULES:
1. Return ONLY valid JSON. No markdown, no explanation, no extra text.
2. NO background box — box must always be false.
3. Font size 28–38px only.
4. font_color: white always.
5. Shadow mandatory: shadow_x 2–4, shadow_y 2–4, shadow_color black@0.85.
6. Position: "center" always.
7. Each overlay lasts 2–4 seconds. Leave 0.5s gap between overlays."""

# ── Prompt template ────────────────────────────────────────────────────────────

CAPTION_PROMPT_TEMPLATE = """Video context analysis:
{context_json}

Video duration: {duration:.2f} seconds.
Best moment time range (from analysis): {best_moment_range}
Best moment start (seconds): {best_moment_start:.2f}
Best moment end (seconds): {best_moment_end:.2f}

Write {overlay_count} caption overlay(s) for this reel.

TIMING RULE: Place the caption inside the best moment time range shown above.
set start_time = {best_moment_start:.2f} and end_time to start_time + 3.0 (but never exceed {best_moment_end:.2f}).

Use the mood and emotion_tags to pick the right vibe — keep the text short and casual like a real fan commenting online.
Do NOT use dramatic or motivational language. Sound human.

Return ONLY a JSON array, no markdown:
[
  {{
    "text": "short casual caption",
    "position": "center",
    "start_time": float,
    "end_time": float,
    "font_size": int (28-38),
    "font_color": "white",
    "box": false,
    "box_color": "black@0.0",
    "box_border_width": 0,
    "shadow_x": int (2-4),
    "shadow_y": int (2-4),
    "shadow_color": "black@0.85"
  }}
]"""

# ── Result dataclass ───────────────────────────────────────────────────────────

@dataclass
class CaptionOverlayResult:
    """Wraps generated overlays with metadata for inspection."""
    overlays: list[TextOverlay]
    raw_llm_response: str
    analysis_mood: str
    analysis_scene_type: str

    def to_dict(self) -> dict:
        return {
            "analysis_mood": self.analysis_mood,
            "analysis_scene_type": self.analysis_scene_type,
            "overlays": [
                {
                    "text": o.text,
                    "position": o.position,
                    "start_time": o.start_time,
                    "end_time": o.end_time,
                    "font_size": o.font_size,
                    "font_color": o.font_color,
                    "box": o.box,
                    "box_color": o.box_color,
                    "box_border_width": o.box_border_width,
                    "shadow_x": o.shadow_x,
                    "shadow_y": o.shadow_y,
                    "shadow_color": o.shadow_color,
                }
                for o in self.overlays
            ],
        }


# ── Engine ─────────────────────────────────────────────────────────────────────

class ReelCaptionEngine:
    """
    Generates TextOverlay objects from a VideoContextAnalysis using an LLM.

    The LLM receives the analysis (mood, pace, intensity, etc.) and video
    duration, then returns a list of overlay specs which are validated and
    converted to TextOverlay instances ready for VideoTextEngine.

    Args:
        llm: LLM instance to use. If None, built from env via create_llm_from_env()
             but with the caption-specific system prompt injected.
        overlay_count: How many caption overlays to request (default 1).
        prompt_template: Override the built-in caption prompt template.
    """

    def __init__(
        self,
        llm: Optional[LLM] = None,
        overlay_count: int = 1,
        prompt_template: Optional[str] = None,
    ) -> None:
        load_dotenv()

        if llm is not None:
            # Always inject the caption-specific system prompt, regardless of what was passed in
            system = os.getenv("CAPTION_SYSTEM_PROMPT") or CAPTION_SYSTEM_PROMPT
            self._llm = LLM(
                api_key=llm._provider.config.get_api_key(),
                model_name=llm.model_name,
                system_prompt=system,
                temperature=llm._provider.config.temperature,
                max_tokens=llm._provider.config.max_tokens,
                timeout=llm._provider.config.timeout,
            )
        else:
            # Build from env but force caption system prompt
            base = create_llm_from_env()
            system = (
                os.getenv("CAPTION_SYSTEM_PROMPT")
                or CAPTION_SYSTEM_PROMPT
            )
            self._llm = LLM(
                api_key=base._provider.config.get_api_key(),
                model_name=base.model_name,
                system_prompt=system,
                temperature=base._provider.config.temperature,
                max_tokens=base._provider.config.max_tokens,
                timeout=base._provider.config.timeout,
            )

        self.overlay_count = max(1, overlay_count)
        self._prompt_template = (
            prompt_template
            or os.getenv("CAPTION_PROMPT_TEMPLATE")
            or CAPTION_PROMPT_TEMPLATE
        )

    def generate(
        self,
        analysis: VideoContextAnalysis,
        video_duration: float = 10.0,
    ) -> CaptionOverlayResult:
        """
        Generate TextOverlay objects from a VideoContextAnalysis.

        Args:
            analysis: Structured result from VideoContextAnalyzer.analyze().
            video_duration: Total duration of the video in seconds.
                            Used so the LLM can choose sensible start/end times.

        Returns:
            CaptionOverlayResult with overlays list and metadata.
        """
        # Resolve best_moment time range → concrete seconds
        time_range = (analysis.best_moment or {}).get("time_range", "unclear")
        if time_range == "first_3_seconds":
            bm_start, bm_end = 0.5, min(3.5, video_duration)
        elif time_range == "last_3_seconds":
            bm_start, bm_end = max(0.0, video_duration - 3.5), video_duration - 0.3
        elif time_range == "both":
            bm_start, bm_end = 0.5, min(3.5, video_duration)   # default to first hook
        else:  # unclear — place in the middle third
            bm_start = video_duration * 0.33
            bm_end   = video_duration * 0.66

        prompt = self._prompt_template.format(
            context_json=json.dumps(analysis.to_dict(), indent=2),
            duration=video_duration,
            overlay_count=self.overlay_count,
            best_moment_range=time_range,
            best_moment_start=bm_start,
            best_moment_end=bm_end,
        )

        logger.debug(f"Requesting {self.overlay_count} caption overlay(s) from LLM")
        raw = self._llm.ask(prompt)
        logger.debug(f"LLM caption response received ({len(raw)} chars)")

        overlays = self._parse_and_build(raw, video_duration, bm_start=bm_start, bm_end=bm_end)
        logger.info(f"Generated {len(overlays)} caption overlay(s): {[o.text for o in overlays]}")

        return CaptionOverlayResult(
            overlays=overlays,
            raw_llm_response=raw,
            analysis_mood=analysis.mood,
            analysis_scene_type=analysis.scene_type,
        )

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _parse_and_build(self, raw: str, video_duration: float, bm_start: float = 0.0, bm_end: float | None = None) -> list[TextOverlay]:
        """Parse LLM JSON response and build validated TextOverlay list."""
        text = raw.strip()
        # Strip markdown fences if present
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1]).strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM returned invalid JSON for captions: {e}\nRaw: {raw[:300]}") from e

        if not isinstance(data, list):
            raise ValueError(f"Expected JSON array of overlays, got: {type(data).__name__}")

        overlays: list[TextOverlay] = []
        for i, item in enumerate(data):
            try:
                overlays.append(self._build_overlay(item, i, video_duration, bm_start=bm_start, bm_end=bm_end or video_duration))
            except (KeyError, TypeError, ValueError) as e:
                raise ValueError(f"Overlay #{i} is invalid: {e}") from e

        if not overlays:
            raise ValueError("LLM returned an empty overlay list")

        return overlays

    def _build_overlay(self, item: dict, idx: int, video_duration: float, bm_start: float = 0.0, bm_end: float | None = None) -> TextOverlay:
        """Validate and build a single TextOverlay from a parsed dict."""
        text = str(item.get("text", "")).strip()
        if not text:
            raise ValueError("text cannot be empty")

        raw_pos = str(item.get("position", "center")).lower().strip()
        if raw_pos not in ("up", "center", "down"):
            logger.warning(f"Overlay #{idx}: unknown position '{raw_pos}', defaulting to 'center'")
            raw_pos = "center"
        position: VerticalPosition = raw_pos  # type: ignore[assignment]

        bm_end = bm_end or video_duration
        # Show caption for the full video duration
        start_time = 0.0
        end_time   = video_duration

        # Outline style (like anime subtitles): white text + black border, no box
        font_size        = max(28, min(42, int(item.get("font_size", 36))))
        font_color       = "white"
        box              = False
        box_color        = "black@0.0"
        box_border_width = 0
        shadow_x         = 2
        shadow_y         = 2
        shadow_color     = "black@0.8"
        border_width     = 3          # thick outline — the key visual element
        border_color     = "black"

        return TextOverlay(
            text=text,
            position=position,
            start_time=start_time,
            end_time=end_time,
            font_size=font_size,
            font_color=font_color,
            box=box,
            box_color=box_color,
            box_border_width=box_border_width,
            shadow_x=shadow_x,
            shadow_y=shadow_y,
            shadow_color=shadow_color,
            border_width=border_width,
            border_color=border_color,
        )

    @staticmethod
    def _clamp_time(value: object, minimum: float, maximum: float) -> float:
        try:
            v = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            v = minimum
        return max(minimum, min(v, maximum))
