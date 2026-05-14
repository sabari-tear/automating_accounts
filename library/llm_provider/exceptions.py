"""LLM Provider Exceptions.

Custom exceptions for LLM operations.
"""


class LLMException(Exception):
    """Base exception for LLM operations."""
    pass


class LLMConfigurationError(LLMException):
    """Raised when LLM configuration is invalid."""
    pass


class LLMProviderError(LLMException):
    """Raised when LLM provider operation fails."""
    pass


class LLMProviderNotFoundError(LLMException):
    """Raised when requested LLM provider is not registered."""
    pass


class LLMFrameAnalysisError(LLMException):
    """Raised when frame analysis fails."""
    pass
