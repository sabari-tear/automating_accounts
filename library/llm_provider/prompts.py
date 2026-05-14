"""Prompts for LLM analysis.

Centralized prompt management for video context analysis.
Separate from provider code for easy customization.
"""

# System prompt for video context analysis
SYSTEM_PROMPT = """You are a professional video editor and content analyst specializing in anime edits and reels.

Your task is to analyze video frames and provide structured context for hook text generation.

CRITICAL RULES:
1. Return ONLY valid JSON. No markdown, no explanation, no extra text.
2. Do NOT generate text content or decide text positions.
3. Do NOT suggest render parameters.
4. Focus ONLY on: mood, scene type, emotion, pacing, visual intensity, and style.
5. Base analysis on VISUAL content only, not character/anime names.
6. Be objective and specific."""

# Analysis prompt template
ANALYSIS_PROMPT_TEMPLATE = """Analyze these {frame_count} frames extracted from a short anime edit.

Frame timing:
- Frames 1-3: From seconds 0-3 (opening)
- Frames 4-6: From the last 3 seconds (closing)

Return ONLY this JSON structure (valid JSON, no markdown):
{{
  "summary": "string (2-3 sentences describing the visual content and energy)",
  "mood": "string (enum: hype|sad|dark|funny|emotional|calm|romantic|intense|mysterious|unknown)",
  "scene_type": "string (enum: fight|entrance|transformation|dialogue|emotional|comedy|chase|reveal|death|powerup|unknown)",
  "intensity": "string (enum: low|medium|high|extreme)",
  "pace": "string (enum: slow|medium|fast|very_fast)",
  "visual_style": ["array of visual descriptors (e.g., 'flashy', 'high_contrast', 'motion_heavy', 'dark', 'colorful')"],
  "emotion_tags": ["array of emotion/mood descriptors (e.g., 'aura', 'power', 'tension', 'sadness')"],
  "hook_style_suggestions": ["array from enum: aura|hype|sad|betrayal|villain|transformation|mystery|emotional|funny|generic"],
  "best_moment": {{
    "time_range": "string (enum: first_3_seconds|last_3_seconds|both|unclear)",
    "reason": "string (why this moment is strongest)"
  }},
  "quality_flags": {{
    "flash_heavy": boolean,
    "motion_heavy": boolean,
    "dark_scene": boolean,
    "existing_text_or_subtitles": boolean
  }},
  "confidence": number (0.0 to 1.0)
}}"""


# Enum definitions (used for validation)
MOODS = ["hype", "sad", "dark", "funny", "emotional", "calm", "romantic", "intense", "mysterious", "unknown"]
SCENE_TYPES = ["fight", "entrance", "transformation", "dialogue", "emotional", "comedy", "chase", "reveal", "death", "powerup", "unknown"]
PACES = ["slow", "medium", "fast", "very_fast"]
INTENSITIES = ["low", "medium", "high", "extreme"]
HOOK_STYLES = ["aura", "hype", "sad", "betrayal", "villain", "transformation", "mystery", "emotional", "funny", "generic"]
TIME_RANGES = ["first_3_seconds", "last_3_seconds", "both", "unclear"]
