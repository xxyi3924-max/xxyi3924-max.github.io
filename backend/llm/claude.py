import json
import os
from typing import Any, Callable

import anthropic

from .base import BaseLLM

ORCHESTRATOR_MODEL = "claude-sonnet-4-20250514"
SUBAGENT_MODEL = "claude-haiku-4-5-20251001"


class ClaudeLLM(BaseLLM):
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

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
        messages = [{"role": "user", "content": user_message}]

        while True:
            response = self.client.messages.create(
                model=ORCHESTRATOR_MODEL,
                max_tokens=4096,
                system=system_prompt,
                tools=tools,
                messages=messages,
            )

            # Collect assistant message
            assistant_content = response.content
            messages.append({"role": "assistant", "content": assistant_content})

            # Emit reasoning text blocks
            if on_reasoning:
                for block in assistant_content:
                    if block.type == "text" and block.text.strip():
                        on_reasoning(block.text)

            # Check stop condition
            if response.stop_reason == "end_turn":
                # Extract final JSON verdict from last text block
                for block in reversed(assistant_content):
                    if block.type == "text":
                        return _parse_verdict(block.text)
                return {}

            # Process tool calls
            tool_results = []
            for block in assistant_content:
                if block.type == "tool_use":
                    if on_tool_call:
                        on_tool_call(block.name, block.input)
                    result = tool_executor(block.name, block.input)
                    if on_tool_result:
                        on_tool_result(block.name, result)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    })

            messages.append({"role": "user", "content": tool_results})

    def run_simple(self, system_prompt: str, user_message: str) -> str:
        response = self.client.messages.create(
            model=SUBAGENT_MODEL,
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text


_VERDICT_DEFAULTS = {
    "signal_type": "noise",
    "conviction": "low",
    "explanation": "",
    "watch_for": "",
    "skills_used": [],
    "bullish_divergence": False,
    "cot_crowded": False,
}


def _parse_verdict(text: str) -> dict:
    """Extract JSON verdict from model text. Always returns a complete dict."""
    import re

    # 1. Try ```json ... ``` code fence
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return {**_VERDICT_DEFAULTS, **json.loads(m.group(1))}
        except json.JSONDecodeError:
            pass

    # 2. Try first { ... } block (handles bare JSON with no fence)
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        return {**_VERDICT_DEFAULTS, **json.loads(text[start:end])}
    except (ValueError, json.JSONDecodeError):
        pass

    # 3. Full fallback — preserve LLM text as explanation
    return {**_VERDICT_DEFAULTS, "explanation": text.strip() or "No verdict generated."}
