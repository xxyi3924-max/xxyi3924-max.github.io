import json
import os
from typing import Any, Callable

from openai import OpenAI

from .base import BaseLLM

ORCHESTRATOR_MODEL = "gpt-4o"
SUBAGENT_MODEL = "gpt-4o-mini"


class OpenAILLM(BaseLLM):
    def __init__(self):
        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

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
        # Convert Anthropic-style tool schemas to OpenAI function format
        oai_tools = [_to_openai_tool(t) for t in tools]

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        while True:
            response = self.client.chat.completions.create(
                model=ORCHESTRATOR_MODEL,
                messages=messages,
                tools=oai_tools,
            )

            msg = response.choices[0].message
            messages.append(msg)

            # Emit reasoning
            if on_reasoning and msg.content:
                on_reasoning(msg.content)

            # Check stop condition
            if response.choices[0].finish_reason == "stop":
                return _parse_verdict(msg.content or "")

            # Process tool calls
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    name = tc.function.name
                    args = json.loads(tc.function.arguments)
                    if on_tool_call:
                        on_tool_call(name, args)
                    result = tool_executor(name, args)
                    if on_tool_result:
                        on_tool_result(name, result)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result),
                    })

    def run_simple(self, system_prompt: str, user_message: str) -> str:
        response = self.client.chat.completions.create(
            model=SUBAGENT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        return response.choices[0].message.content


def _to_openai_tool(tool: dict) -> dict:
    """Convert Anthropic tool schema to OpenAI function calling format."""
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": tool.get("input_schema", {"type": "object", "properties": {}}),
        },
    }


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
