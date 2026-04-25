from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable

from llm_client import LLMClient
from memory import ConversationMemory
from tools import ToolRegistry


Printer = Callable[[str], None]


@dataclass
class AgentConfig:
    max_tool_steps: int = 3


class AgentController:
    def __init__(
        self,
        llm: LLMClient,
        memory: ConversationMemory,
        tools: ToolRegistry,
        config: AgentConfig | None = None,
    ) -> None:
        self.llm = llm
        self.memory = memory
        self.tools = tools
        self.config = config or AgentConfig()

    def run_turn(self, user_input: str, print_chunk: Printer = print) -> str:
        self.memory.add("user", user_input)

        for _ in range(self.config.max_tool_steps + 1):
            response = self._collect_response(print_chunk)
            action = self._parse_tool_action(response)
            if action is None:
                print_chunk(response)
                print_chunk("\n")
                self.memory.add("assistant", response)
                return response

            tool_name = action["action"]
            args = action["args"]
            tool = self.tools.get(tool_name)
            if tool is None:
                self.memory.add("tool", f"Unknown tool: {tool_name}")
                continue

            try:
                result = tool.run(args)
            except Exception as exc:
                result = f"Tool {tool_name} failed: {exc}"
            self.memory.add("assistant", response)
            self.memory.add("tool", result)

        message = "Tool loop stopped: max_tool_steps reached."
        print_chunk(message)
        print_chunk("\n")
        self.memory.add("assistant", message)
        return message

    def _collect_response(self, print_chunk: Printer) -> str:
        chunks: list[str] = []
        should_stream: bool | None = None
        for chunk in self.llm.stream_chat(self._messages_for_llm()):
            chunks.append(chunk)
            if should_stream is None:
                stripped = "".join(chunks).lstrip()
                if not stripped:
                    continue
                should_stream = not stripped.startswith("{")
                if should_stream:
                    print_chunk("".join(chunks))
                    continue
            elif should_stream:
                print_chunk(chunk)
        return "".join(chunks).strip()

    def _messages_for_llm(self) -> list[dict[str, str]]:
        return self.memory.messages(self._system_prompt_with_tools())

    def _system_prompt_with_tools(self) -> str:
        return f"""{self.memory.system_prompt}

Available tools:
{self.tools.prompt_descriptions()}

Tool calling rules:
- If no tool is needed, answer normally.
- If a tool is needed, return ONLY valid JSON with this shape:
  {{"action": "tool_name", "args": {{}}}}
- Do not include markdown fences, comments, or extra text when calling a tool.
"""

    @staticmethod
    def _parse_tool_action(text: str) -> dict[str, object] | None:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return None

        if not isinstance(data, dict):
            return None
        action = data.get("action")
        args = data.get("args", {})
        if not isinstance(action, str) or not isinstance(args, dict):
            return None
        return {"action": action, "args": args}
