from abc import ABC, abstractmethod
from typing import Any, Callable


class BaseLLM(ABC):
    """Unified interface for all LLM providers."""

    @abstractmethod
    def run_agent_loop(
        self,
        system_prompt: str,
        user_message: str,
        tools: list[dict],
        tool_executor: Callable[[str, dict], Any],
        on_reasoning: Callable[[str], None] | None = None,
        on_tool_call: Callable[[str, dict], None] | None = None,
        on_tool_result: Callable[[str, Any], None] | None = None,
    ) -> dict:
        """
        Run a tool-use agentic loop until the model stops calling tools.
        Returns the final verdict dict parsed from the last assistant message.
        """
        ...

    @abstractmethod
    def run_simple(self, system_prompt: str, user_message: str) -> str:
        """Single-turn completion — used for cheap sub-agent tasks (e.g. social_buzz)."""
        ...
