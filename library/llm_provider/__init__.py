"""LLM Provider Library.

Extensible LLM client abstraction with pluggable providers.
Supports Google Gemini, OpenAI GPT-4 Vision, and custom providers.

Quick start::

    from library.llm_provider import LLM

    # Create an instance once — api_key, model, and system_prompt baked in
    llm = LLM(
        api_key="YOUR_API_KEY",
        model_name="gemini-2.0-flash",
        system_prompt="You are a helpful assistant.",
    )

    # Text generation (caption, summary, etc.)
    caption = llm.ask("Describe this sunset reel in one punchy line.")

    # Pass to VideoContextAnalyzer
    from library.video_context_analyzer import VideoContextAnalyzer
    analyzer = VideoContextAnalyzer(llm=llm)
    result = analyzer.analyze("clip.mp4")
"""

from .config import LLMConfig, DEFAULT_LLM_CONFIG
from .exceptions import (
    LLMException,
    LLMConfigurationError,
    LLMProviderError,
    LLMProviderNotFoundError,
    LLMFrameAnalysisError,
)
from .prompts import (
    SYSTEM_PROMPT,
    ANALYSIS_PROMPT_TEMPLATE,
    MOODS,
    SCENE_TYPES,
    PACES,
    INTENSITIES,
    HOOK_STYLES,
    TIME_RANGES,
)
from .provider import (
    LLM,
    LLMProvider,
    GoogleGeminiProvider,
    OpenAIProvider,
    register_provider,
    get_provider_class,
    create_provider,
    create_provider_with_params,
    create_llm_from_env,
    list_available_providers,
    infer_provider_from_model,
    prompt_llm,
)

__all__ = [
    # Primary user-facing interface
    "LLM",
    # Configuration
    "LLMConfig",
    "DEFAULT_LLM_CONFIG",
    # Exceptions
    "LLMException",
    "LLMConfigurationError",
    "LLMProviderError",
    "LLMProviderNotFoundError",
    "LLMFrameAnalysisError",
    # Prompts & Enums
    "SYSTEM_PROMPT",
    "ANALYSIS_PROMPT_TEMPLATE",
    "MOODS",
    "SCENE_TYPES",
    "PACES",
    "INTENSITIES",
    "HOOK_STYLES",
    "TIME_RANGES",
    # Provider base and implementations
    "LLMProvider",
    "GoogleGeminiProvider",
    "OpenAIProvider",
    # Factory and registry
    "register_provider",
    "get_provider_class",
    "create_provider",
    "create_provider_with_params",
    "create_llm_from_env",
    "list_available_providers",
    "infer_provider_from_model",
    "prompt_llm",
]
