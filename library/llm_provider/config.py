"""LLM Provider Configuration.

Type-safe configuration management for LLM providers.
Supports validation and environment variable resolution.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMConfig:
    """Type-safe LLM configuration."""
    
    provider: str
    """LLM provider name (google, openai, anthropic, custom)"""
    
    model: str
    """Model identifier (e.g., 'gemini-2.0-flash', 'gpt-4-vision')"""
    
    temperature: float = 0.3
    """Temperature for response generation (0.0 = deterministic, 1.0 = creative)"""
    
    max_tokens: int = 2000
    """Maximum tokens in LLM response"""
    
    timeout: int = 30
    """Request timeout in seconds"""
    
    api_key: Optional[str] = None
    """API key (if None, reads from environment variable)"""
    
    api_key_env_var: str = "GEMINI_API_KEY"
    """Environment variable name for API key"""
    
    def get_api_key(self) -> str:
        """Get API key from config or environment."""
        if self.api_key:
            return self.api_key
        
        api_key = os.getenv(self.api_key_env_var)
        if not api_key:
            raise ValueError(
                f"API key not found. Set '{self.api_key_env_var}' environment variable "
                f"or pass api_key to LLMConfig"
            )
        return api_key
    
    def validate(self) -> None:
        """Validate configuration."""
        if not self.provider:
            raise ValueError("provider cannot be empty")
        if not self.model:
            raise ValueError("model cannot be empty")
        if not 0.0 <= self.temperature <= 1.0:
            raise ValueError(f"temperature must be between 0.0 and 1.0, got {self.temperature}")
        if self.max_tokens < 1:
            raise ValueError(f"max_tokens must be >= 1, got {self.max_tokens}")
        if self.timeout < 1:
            raise ValueError(f"timeout must be >= 1, got {self.timeout}")


# Default configuration (can be overridden)
DEFAULT_LLM_CONFIG = LLMConfig(
    provider="google",
    model="gemini-2.0-flash",
    temperature=0.3,
    max_tokens=2000,
    timeout=30,
    api_key_env_var="GEMINI_API_KEY",
)
