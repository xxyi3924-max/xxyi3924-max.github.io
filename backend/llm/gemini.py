import json
import os
from typing import Any, Callable

import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration, Tool

from .base import BaseLLM

ORCHESTRATOR_MODEL = "gemini-2.0-flash"
SUBAGENT_MODEL = "gemini-2.0-flash"


class GeminiLLM(BaseLLM):
    def __init__(self):
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])

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
        gemini_tools = [_to_gemini_tool(tools)]

        model = genai.GenerativeModel(
            model_name=ORCHESTRATOR_MODEL,
            system_instruction=system_prompt,
            tools=gemini_tools,
        )
        chat = model.start_chat()

        response = chat.send_message(user_message)

        while True:
            part = response.candidates[0].content.parts[0]

            # Text response — done
            if hasattr(part, "text"):
                if on_reasoning and part.text.strip():
                    on_reasoning(part.text)
                return _parse_verdict(part.text)

            # Function call
            if hasattr(part, "function_call"):
                fc = part.function_call
                args = dict(fc.args)
                if on_tool_call:
                    on_tool_call(fc.name, args)
                result = tool_executor(fc.name, args)
                if on_tool_result:
                    on_tool_result(fc.name, result)

                response = chat.send_message(
                    genai.protos.Content(parts=[
                        genai.protos.Part(
                            function_response=genai.protos.FunctionResponse(
                                name=fc.name,
                                response={"result": json.dumps(result)},
                            )
                        )
                    ])
                )

    def run_simple(self, system_prompt: str, user_message: str) -> str:
        model = genai.GenerativeModel(
            model_name=SUBAGENT_MODEL,
            system_instruction=system_prompt,
        )
        response = model.generate_content(user_message)
        return response.text


def _to_gemini_tool(tools: list[dict]) -> Tool:
    """Convert Anthropic-style tool schemas to a Gemini Tool object."""
    declarations = []
    for t in tools:
        schema = t.get("input_schema", {})
        declarations.append(FunctionDeclaration(
            name=t["name"],
            description=t.get("description", ""),
            parameters=schema,
        ))
    return Tool(function_declarations=declarations)


def _parse_verdict(text: str) -> dict:
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        return json.loads(text[start:end])
    except (ValueError, json.JSONDecodeError):
        return {"explanation": text}
