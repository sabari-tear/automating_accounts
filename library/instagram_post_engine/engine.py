"""Instagram Post Engine — core implementation.

Converts a VideoContextAnalysis into a ready-to-paste Instagram Reels post:
  - A punchy caption tailored to the video mood
  - A hashtag block (niche + medium + broad tags)
  - Full post_text ready to copy-paste when uploading
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from library.llm_provider import LLM, create_llm_from_env
from library.video_context_analyzer import VideoContextAnalysis

logger = logging.getLogger(__name__)

# ── System prompt ──────────────────────────────────────────────────────────────

INSTAGRAM_SYSTEM_PROMPT = """You are an Instagram Reels growth strategist for anime edit accounts.
You write post captions that drive saves, comments, and follows.

Rules for caption:
- 1-3 short lines. Casual, specific to the vibe of the video. NOT motivational or generic.
- End with a comment CTA to boost engagement (e.g. "who is your fav?" / "drop a 🔥 if you fw this" / "name a better scene 💀")
- No hashtags in the caption block.

Rules for hashtags:
- 25-30 tags total, NO # prefix in the array
- Mix: 5 niche tags (under 500k posts), 15 medium (500k–5M), 5 broad (over 5M)
- Always include: animeedit, animetok, animereels, fyp, reels
- Tailor the rest to the detected mood and scene type

TECHNICAL RULES:
1. Return ONLY valid JSON. No markdown, no explanation.
2. post_text must be the complete ready-to-paste string:
   caption text, then two newlines, then all hashtags space-separated with # prefix."""

# ── Prompt template ────────────────────────────────────────────────────────────

INSTAGRAM_PROMPT_TEMPLATE = """Video context analysis:
{context_json}

Generate a complete Instagram Reels post for this anime edit.

Return ONLY this JSON (no markdown fences):
{{
  "caption": "the caption text (1-3 lines, ends with a comment CTA)",
  "hashtags": ["list", "of", "tags", "without", "hash", "prefix"],
  "post_text": "caption line(s)\\n\\n#tag1 #tag2 #tag3 ..."
}}"""

# ── Result dataclass ───────────────────────────────────────────────────────────


@dataclass
class InstagramPost:
    """A ready-to-paste Instagram Reels post."""

    caption: str
    hashtags: list[str]
    post_text: str

    def save(self, path: str | Path) -> None:
        """Save the full post text to a .txt file."""
        Path(path).write_text(self.post_text, encoding="utf-8")
        logger.info(f"Instagram post saved: {path}")

    def preview(self) -> str:
        """Return a short preview string for logging."""
        tag_count = len(self.hashtags)
        caption_preview = self.caption[:80] + ("..." if len(self.caption) > 80 else "")
        return f'Caption: "{caption_preview}" | {tag_count} hashtags'


# ── Engine ─────────────────────────────────────────────────────────────────────


class InstagramPostEngine:
    """
    Generates a ready-to-paste Instagram Reels post from a VideoContextAnalysis.

    Produces a punchy caption tailored to the video mood + a hashtag block
    mixing niche, medium, and broad anime edit tags.

    Args:
        llm: LLM instance to use. If None, built from env via create_llm_from_env().
        prompt_template: Override the built-in prompt template.
    """

    def __init__(
        self,
        llm: Optional[LLM] = None,
        prompt_template: Optional[str] = None,
    ) -> None:
        load_dotenv()

        system = os.getenv("INSTAGRAM_SYSTEM_PROMPT") or INSTAGRAM_SYSTEM_PROMPT

        if llm is not None:
            self._llm = LLM(
                api_key=llm._provider.config.get_api_key(),
                model_name=llm.model_name,
                system_prompt=system,
                temperature=0.8,
                max_tokens=1000,
            )
        else:
            base = create_llm_from_env()
            self._llm = LLM(
                api_key=base._provider.config.get_api_key(),
                model_name=base.model_name,
                system_prompt=system,
                temperature=0.8,
                max_tokens=1000,
            )

        self._prompt_template = (
            prompt_template
            or os.getenv("INSTAGRAM_PROMPT_TEMPLATE")
            or INSTAGRAM_PROMPT_TEMPLATE
        )

    def generate(self, analysis: VideoContextAnalysis) -> InstagramPost:
        """
        Generate an Instagram post from a VideoContextAnalysis.

        Args:
            analysis: Structured result from VideoContextAnalyzer.analyze().

        Returns:
            InstagramPost with caption, hashtags, and full post_text.
        """
        prompt = self._prompt_template.format(
            context_json=json.dumps(analysis.to_dict(), indent=2),
        )

        logger.debug("Requesting Instagram post from LLM")
        raw = self._llm.ask(prompt)
        logger.debug(f"Instagram post LLM response ({len(raw)} chars)")

        return self._parse(raw)

    def _parse(self, raw: str) -> InstagramPost:
        """Parse LLM JSON response into an InstagramPost."""
        text = raw.strip()
        # Strip markdown fences if present
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1]).strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"LLM returned invalid JSON for Instagram post: {e}\nRaw: {raw[:300]}"
            ) from e

        return InstagramPost(
            caption=str(data.get("caption", "")),
            hashtags=list(data.get("hashtags", [])),
            post_text=str(data.get("post_text", "")),
        )
