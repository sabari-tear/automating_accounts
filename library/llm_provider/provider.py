"""LLM Provider Base and Implementations.

Abstract base class and concrete implementations for different LLM providers.
Extensible registry pattern for easy addition of new providers.
"""

import logging
import os
from abc import ABC, abstractmethod
from typing import Optional

from .config import LLMConfig
from .exceptions import LLMConfigurationError, LLMFrameAnalysisError

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    def __init__(self, config: LLMConfig):
        """
        Initialize LLM provider.
        
        Args:
            config: LLMConfig instance
            
        Raises:
            LLMConfigurationError: If configuration is invalid
        """
        config.validate()
        self.config = config
        logger.debug(f"Initialized {self.__class__.__name__} with model {config.model}")
    
    @abstractmethod
    def analyze_frames(self, frames_base64: list[str], prompt: str) -> str:
        """
        Send frames and analysis prompt to LLM.
        
        Args:
            frames_base64: List of base64-encoded frame images (JPEG)
            prompt: Analysis prompt with instructions and JSON schema
            
        Returns:
            LLM response text (should be valid JSON)
            
        Raises:
            LLMFrameAnalysisError: If frame analysis fails
        """
        pass

    def generate(self, user_prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate a text response for a user prompt."""
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement text generation"
        )


class GoogleGeminiProvider(LLMProvider):
    """Google Gemini LLM provider (google-genai SDK)."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        try:
            import google.genai as genai
            from google.genai import types as genai_types
            self.client = genai.Client(api_key=config.get_api_key())
            self.genai_types = genai_types
            logger.info(f"Google Gemini initialized with model: {config.model}")
        except ImportError as e:
            raise LLMConfigurationError(
                "google-genai not installed. "
                "Install with: pip install google-genai"
            ) from e

    def analyze_frames(self, frames_base64: list[str], prompt: str) -> str:
        """Send frames to Google Gemini API."""
        import base64
        if not frames_base64:
            raise LLMFrameAnalysisError("No frames provided for analysis")

        try:
            types = self.genai_types
            parts = [types.Part.from_text(text=prompt)]
            for i, frame_b64 in enumerate(frames_base64):
                try:
                    parts.append(
                        types.Part.from_bytes(
                            data=base64.b64decode(frame_b64),
                            mime_type="image/jpeg",
                        )
                    )
                except Exception as e:
                    logger.warning(f"Failed to add frame {i} to message: {e}")

            logger.debug(f"Sending {len(frames_base64)} frames to Gemini")
            response = self.client.models.generate_content(
                model=self.config.model,
                contents=parts,
                config=types.GenerateContentConfig(
                    temperature=self.config.temperature,
                    max_output_tokens=self.config.max_tokens,
                ),
            )
            logger.debug("Received response from Gemini")
            return response.text
        except Exception as e:
            raise LLMFrameAnalysisError(f"Google Gemini analysis failed: {e}") from e

    def generate(self, user_prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate text with Google Gemini."""
        if not user_prompt or not user_prompt.strip():
            raise LLMFrameAnalysisError("user_prompt cannot be empty")

        try:
            types = self.genai_types
            prompt = user_prompt.strip()
            if system_prompt and system_prompt.strip():
                prompt = f"{system_prompt.strip()}\n\n{prompt}"

            response = self.client.models.generate_content(
                model=self.config.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=self.config.temperature,
                    max_output_tokens=self.config.max_tokens,
                ),
            )
            return response.text
        except Exception as e:
            raise LLMFrameAnalysisError(f"Google Gemini text generation failed: {e}") from e


class OpenAIProvider(LLMProvider):
    """OpenAI GPT-4 Vision provider."""
    
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        try:
            from openai import OpenAI
            api_key = config.get_api_key()
            self.client = OpenAI(api_key=api_key)
            logger.info(f"OpenAI initialized with model: {config.model}")
        except ImportError as e:
            raise LLMConfigurationError(
                "openai not installed. "
                "Install with: pip install openai"
            ) from e
    
    def analyze_frames(self, frames_base64: list[str], prompt: str) -> str:
        """Send frames to OpenAI GPT-4 Vision API."""
        if not frames_base64:
            raise LLMFrameAnalysisError("No frames provided for analysis")
        
        try:
            content = [{"type": "text", "text": prompt}]
            for i, frame_b64 in enumerate(frames_base64):
                try:
                    content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{frame_b64}"
                        }
                    })
                except Exception as e:
                    logger.warning(f"Failed to add frame {i} to content: {e}")
                    continue
            
            logger.debug(f"Sending {len(frames_base64)} frames to OpenAI")
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "user", "content": content}
                ],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                timeout=self.config.timeout,
            )
            
            logger.debug("Received response from OpenAI")
            return response.choices[0].message.content
        except Exception as e:
            raise LLMFrameAnalysisError(f"OpenAI analysis failed: {e}") from e

    def generate(self, user_prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate text with OpenAI chat models."""
        if not user_prompt or not user_prompt.strip():
            raise LLMFrameAnalysisError("user_prompt cannot be empty")

        try:
            messages = []
            if system_prompt and system_prompt.strip():
                messages.append({"role": "system", "content": system_prompt.strip()})
            messages.append({"role": "user", "content": user_prompt.strip()})

            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                timeout=self.config.timeout,
            )
            return response.choices[0].message.content
        except Exception as e:
            raise LLMFrameAnalysisError(f"OpenAI text generation failed: {e}") from e


# Provider registry for extensibility
_PROVIDER_REGISTRY = {
    "google": GoogleGeminiProvider,
    "gemini": GoogleGeminiProvider,  # Alias
    "openai": OpenAIProvider,
    "gpt-4-vision": OpenAIProvider,  # Alias
}


def register_provider(name: str, provider_class: type[LLMProvider]) -> None:
    """
    Register a new LLM provider.
    
    Args:
        name: Provider identifier (lowercase)
        provider_class: LLMProvider subclass
        
    Example:
        class MyCustomProvider(LLMProvider):
            def analyze_frames(self, frames_base64, prompt):
                # Custom implementation
                pass
        
        register_provider("custom", MyCustomProvider)
    """
    if not issubclass(provider_class, LLMProvider):
        raise TypeError(f"{provider_class} must be a subclass of LLMProvider")
    _PROVIDER_REGISTRY[name.lower()] = provider_class
    logger.info(f"Registered LLM provider: {name}")


def get_provider_class(provider_name: str) -> type[LLMProvider]:
    """
    Get provider class by name.
    
    Args:
        provider_name: Provider identifier
        
    Returns:
        LLMProvider subclass
        
    Raises:
        LLMProviderNotFoundError: If provider not registered
    """
    from .exceptions import LLMProviderNotFoundError
    
    provider_class = _PROVIDER_REGISTRY.get(provider_name.lower())
    if not provider_class:
        available = ", ".join(_PROVIDER_REGISTRY.keys())
        raise LLMProviderNotFoundError(
            f"Unknown provider: {provider_name}. "
            f"Available: {available}"
        )
    return provider_class


def create_provider(config: Optional[LLMConfig] = None) -> LLMProvider:
    """
    Factory function to create LLM provider instance.
    
    Args:
        config: LLMConfig instance. If None, uses defaults.
        
    Returns:
        Initialized LLMProvider instance
        
    Raises:
        LLMConfigurationError: If configuration is invalid
        LLMProviderNotFoundError: If provider not found
        
    Example:
        from library.llm_provider import create_provider, LLMConfig
        
        config = LLMConfig(provider="openai", model="gpt-4-vision")
        provider = create_provider(config)
        response = provider.analyze_frames([frame1, frame2], prompt)
    """
    from .config import DEFAULT_LLM_CONFIG
    
    if config is None:
        config = DEFAULT_LLM_CONFIG
    
    provider_class = get_provider_class(config.provider)
    return provider_class(config)


def create_provider_with_params(
    *,
    provider: str,
    model_name: str,
    api_key: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 2000,
    timeout: int = 30,
    api_key_env_var: Optional[str] = None,
) -> LLMProvider:
    """Create an LLM provider directly from simple parameters."""
    config = LLMConfig(
        provider=provider,
        model=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        api_key=api_key,
        api_key_env_var=api_key_env_var or "GEMINI_API_KEY",
    )
    return create_provider(config)


def infer_provider_from_model(model_name: str) -> str:
    """Infer provider from model name when provider is not explicitly provided."""
    normalized = model_name.lower().strip()
    if normalized.startswith(("gpt", "o1", "o3")):
        return "openai"
    if "gemini" in normalized:
        return "google"
    return "google"


def _load_dotenv() -> None:
    """Load .env values when python-dotenv is available."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        # Keep env loading optional; os.environ can still be used directly.
        pass


def create_llm_from_env() -> "LLM":
    """
    Create an LLM instance from environment variables.

    Environment variables:
    - LLM_MODEL_NAME (default: gemini-2.0-flash)
    - LLM_SYSTEM_PROMPT (default: empty string)
    - LLM_PROVIDER (optional; inferred from model when omitted)
    - LLM_TEMPERATURE (default: 0.3)
    - LLM_MAX_TOKENS (default: 2000)
    - LLM_TIMEOUT (default: 30)
    - LLM_API_KEY (optional generic key)
    - GEMINI_API_KEY / OPENAI_API_KEY (provider-specific fallback)
    """
    _load_dotenv()

    model_name = os.getenv("LLM_MODEL_NAME", "gemini-2.0-flash").strip()
    if not model_name:
        model_name = "gemini-2.0-flash"

    system_prompt = os.getenv("LLM_SYSTEM_PROMPT", "")
    provider_name = os.getenv("LLM_PROVIDER")
    selected_provider = provider_name.strip().lower() if provider_name else infer_provider_from_model(model_name)

    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY") if selected_provider == "openai" else os.getenv("GEMINI_API_KEY")

    if not api_key:
        expected_key = "OPENAI_API_KEY" if selected_provider == "openai" else "GEMINI_API_KEY"
        raise LLMConfigurationError(
            f"API key not found. Set LLM_API_KEY or {expected_key} in environment/.env"
        )

    try:
        temperature = float(os.getenv("LLM_TEMPERATURE", "0.3"))
    except ValueError as e:
        raise LLMConfigurationError("LLM_TEMPERATURE must be a valid float") from e

    try:
        max_tokens = int(os.getenv("LLM_MAX_TOKENS", "2000"))
    except ValueError as e:
        raise LLMConfigurationError("LLM_MAX_TOKENS must be a valid integer") from e

    try:
        timeout = int(os.getenv("LLM_TIMEOUT", "30"))
    except ValueError as e:
        raise LLMConfigurationError("LLM_TIMEOUT must be a valid integer") from e

    return LLM(
        api_key=api_key,
        model_name=model_name,
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
    )


def prompt_llm(
    *,
    api_key: Optional[str],
    model_name: str,
    system_prompt: Optional[str],
    user_prompt: str = "",
    provider: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 2000,
    timeout: int = 30,
) -> str:
    """Simple one-call helper to get an LLM response for text use cases."""
    effective_user_prompt = user_prompt.strip() or "Please follow the system instructions and respond accordingly."
    selected_provider = provider or infer_provider_from_model(model_name)
    llm_provider = create_provider_with_params(
        provider=selected_provider,
        model_name=model_name,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        api_key_env_var="OPENAI_API_KEY" if selected_provider == "openai" else "GEMINI_API_KEY",
    )
    return llm_provider.generate(user_prompt=effective_user_prompt, system_prompt=system_prompt)


def list_available_providers() -> list[str]:
    """
    Get list of available providers.
    
    Returns:
        List of provider names
    """
    return sorted(set(
        name for name in _PROVIDER_REGISTRY.keys()
        if not name in ["gemini", "gpt-4-vision"]  # Hide aliases
    ))


class LLM:
    """
    User-facing LLM instance. Create once with your credentials and system prompt,
    then pass to any library or call directly.

    Example — text generation (caption, summary, etc.)::

        from library.llm_provider import LLM

        llm = LLM(
            api_key="YOUR_KEY",
            model_name="gemini-2.0-flash",
            system_prompt="You write punchy captions for Instagram reels.",
        )
        caption = llm.ask("The clip shows a golden-hour surf session in Bali.")

    Example — video context analysis::

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

    def __init__(
        self,
        *,
        api_key: str,
        model_name: str,
        system_prompt: str = "",
        temperature: float = 0.3,
        max_tokens: int = 2000,
        timeout: int = 30,
    ) -> None:
        provider_name = infer_provider_from_model(model_name)
        config = LLMConfig(
            provider=provider_name,
            model=model_name,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            api_key_env_var="OPENAI_API_KEY" if provider_name == "openai" else "GEMINI_API_KEY",
        )
        self._provider: LLMProvider = create_provider(config)
        self.system_prompt = system_prompt
        self.model_name = model_name
        logger.debug(f"LLM ready: provider={provider_name}, model={model_name}")

    def ask(self, user_prompt: str) -> str:
        """
        Send a user prompt and get a text response.
        The system_prompt you set at construction is automatically included.

        Args:
            user_prompt: The user-side instruction or content.

        Returns:
            LLM response string.
        """
        if not user_prompt or not user_prompt.strip():
            raise ValueError("user_prompt cannot be empty")
        return self._provider.generate(
            user_prompt=user_prompt,
            system_prompt=self.system_prompt or None,
        )

    def analyze_frames(self, frames_base64: list[str], prompt: str) -> str:
        """
        Send video frames to the LLM for analysis.
        Used internally by VideoContextAnalyzer — you normally don't call this directly.

        Args:
            frames_base64: List of base64-encoded JPEG frames.
            prompt: Analysis instruction / JSON schema prompt.

        Returns:
            LLM response string (typically JSON).
        """
        effective_prompt = prompt
        if self.system_prompt and self.system_prompt.strip():
            effective_prompt = f"{self.system_prompt.strip()}\n\n{prompt}"
        return self._provider.analyze_frames(frames_base64, effective_prompt)
