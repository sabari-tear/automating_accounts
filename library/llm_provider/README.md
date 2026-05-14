# LLM Provider

Unified LLM layer for this project.

Use this library when you want to:
- Create reusable LLM instances with api_key + model_name + system_prompt.
- Reuse the same instance across multiple workflows.
- Support different scenarios with different system prompts (context analysis, captions, summaries, etc.).
- Switch between Google Gemini and OpenAI models with a common interface.

## Primary Usage Pattern

Create one LLM instance and pass it where needed.

```python
from library.llm_provider import LLM

llm = LLM(
    api_key="YOUR_API_KEY",
    model_name="gemini-2.0-flash",
    system_prompt="You are an expert video analyst.",
)

result = llm.ask("Summarize this clip in 2 lines.")
```

For a different scenario, create another instance with a different system_prompt.

```python
caption_llm = LLM(
    api_key="YOUR_API_KEY",
    model_name="gemini-2.0-flash",
    system_prompt="You write short viral reel captions.",
)

caption = caption_llm.ask("Golden-hour surf shot with cinematic slow motion")
```

## Environment-Driven Usage (clean default flow)

If you prefer no hardcoded model/prompt values in code, configure .env and let the analyzer build the LLM automatically.

Required or commonly used env keys:
- GEMINI_API_KEY or OPENAI_API_KEY
- LLM_MODEL_NAME
- LLM_SYSTEM_PROMPT
- LLM_PROVIDER (optional)
- LLM_TEMPERATURE (optional)
- LLM_MAX_TOKENS (optional)
- LLM_TIMEOUT (optional)
- VIDEO_CONTEXT_ANALYSIS_PROMPT_TEMPLATE (optional, must include {frame_count})

Then use:

```python
from library.video_context_analyzer import VideoContextAnalyzer

analyzer = VideoContextAnalyzer()  # Auto-loads env and creates LLM internally
analysis = analyzer.analyze("test/sample_input_videos/example.mp4")
```

You can also construct the env-based instance directly:

```python
from library.llm_provider import create_llm_from_env

llm = create_llm_from_env()
```

## Integration with Video Context Analyzer

```python
from library.llm_provider import LLM
from library.video_context_analyzer import VideoContextAnalyzer

llm = LLM(
    api_key="YOUR_API_KEY",
    model_name="gemini-2.0-flash",
    system_prompt="You are an expert video analyst.",
)

analyzer = VideoContextAnalyzer(llm=llm)
analysis = analyzer.analyze("test/sample_input_videos/example.mp4")
```

## Installation

Install project dependencies:

```bash
pip install -r requirements.txt
```

Provider specific requirements:
- Google Gemini: google-generativeai
- OpenAI: openai

## Provider Selection Rules

Provider is inferred from model_name in LLM constructor:
- model starts with gpt, o1, o3 -> openai
- model contains gemini -> google
- fallback -> google

You can still use lower-level APIs to force provider manually.

## Public API Reference

### 1. LLM (recommended)

Constructor:

```python
LLM(
    api_key: str,
    model_name: str,
    system_prompt: str = "",
    temperature: float = 0.3,
    max_tokens: int = 2000,
    timeout: int = 30,
)
```

Methods:
- ask(user_prompt: str) -> str
- analyze_frames(frames_base64: list[str], prompt: str) -> str

Notes:
- ask always uses the system_prompt configured in the instance.
- analyze_frames is mainly used by VideoContextAnalyzer.

### 2. prompt_llm (single-call helper)

```python
prompt_llm(
    api_key: str | None,
    model_name: str,
    system_prompt: str | None,
    user_prompt: str = "",
    provider: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 2000,
    timeout: int = 30,
) -> str
```

Use this when you do not need a reusable instance.

### 3. create_provider_with_params (advanced)

```python
create_provider_with_params(
    provider: str,
    model_name: str,
    api_key: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 2000,
    timeout: int = 30,
    api_key_env_var: str | None = None,
) -> LLMProvider
```

### 4. create_provider with LLMConfig (advanced)

```python
from library.llm_provider import LLMConfig, create_provider

cfg = LLMConfig(
    provider="openai",
    model="gpt-4.1-mini",
    api_key="YOUR_API_KEY",
)
provider = create_provider(cfg)
```

### 5. create_llm_from_env (recommended for app defaults)

```python
create_llm_from_env() -> LLM
```

This reads model and prompt settings from environment variables and returns a ready-to-use LLM instance.

## Input and Output Behavior

### Text generation
- Input: system_prompt (at instance construction) + user_prompt (per call).
- Output: plain string from provider response.

### Frame analysis
- Input:
  - frames_base64 list with base64 JPEG strings.
  - prompt that contains analysis instructions and output schema guidance.
- Output: plain string, typically expected to be JSON text when used by VideoContextAnalyzer.

## Error Reference

Exceptions exported by this package:
- LLMException: Base exception.
- LLMConfigurationError: Invalid provider config or missing provider SDK.
- LLMProviderError: Generic provider operation failure.
- LLMProviderNotFoundError: Unknown provider key in registry.
- LLMFrameAnalysisError: Generation or frame analysis request failed.

Validation and runtime errors you may also see:
- ValueError from config validation or empty user_prompt.
- ImportError wrapped as LLMConfigurationError if provider package is missing.

## Available Providers and Registry

Registered provider keys:
- google
- gemini (alias of google)
- openai
- gpt-4-vision (alias of openai)

Inspect available providers:

```python
from library.llm_provider import list_available_providers

print(list_available_providers())
```

Register custom provider:

```python
from library.llm_provider import LLMProvider, register_provider

class MyProvider(LLMProvider):
    def analyze_frames(self, frames_base64, prompt):
        return "{}"

register_provider("custom", MyProvider)
```

## Best Practices

- Create separate LLM instances per scenario with different system prompts.
- Reuse a single instance across methods/libraries for the same scenario.
- Keep temperature lower for deterministic structured tasks (like JSON analysis).
- Keep temperature slightly higher for creative tasks (captions, hooks).
- For video context analysis, keep output schema in prompt strict and explicit.

## Related Files

- Provider implementation: provider.py
- Config model: config.py
- Exceptions: exceptions.py
- Shared analysis prompts: prompts.py
- Machine-readable contract: input_output_contract.json