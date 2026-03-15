import os
from .base import BaseLLM


def get_llm() -> BaseLLM:
    """Factory — returns the correct LLM provider based on LLM_PROVIDER env var."""
    provider = os.getenv("LLM_PROVIDER", "claude").lower()

    if provider == "claude":
        from .claude import ClaudeLLM
        return ClaudeLLM()
    elif provider == "openai":
        from .openai import OpenAILLM
        return OpenAILLM()
    elif provider == "gemini":
        from .gemini import GeminiLLM
        return GeminiLLM()
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: '{provider}'. Choose claude | openai | gemini")
