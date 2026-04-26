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
    # 限制单轮工具调用次数，防止模型输出工具请求后一直循环。
    max_tool_steps: int = 3


class AgentController:
    def __init__(
        self,
        llm: LLMClient,
        memory: ConversationMemory,
        tools: ToolRegistry,
        config: AgentConfig | None = None,
    ) -> None:
        # 控制器只持有执行一轮对话所需的依赖，不直接处理终端输入输出。
        self.llm = llm
        self.memory = memory
        self.tools = tools
        self.config = config or AgentConfig()

    def run_turn(self, user_input: str, print_chunk: Printer = print) -> str:
        # 先把用户输入写入记忆，再交给模型生成下一步响应。
        self.memory.add("user", user_input)

        for _ in range(self.config.max_tool_steps + 1):
            # 每次循环都重新向模型发送完整上下文，包含最新的工具结果。
            response = self._collect_response(print_chunk)
            # 如果模型返回的是工具调用指令，则先执行工具再继续下一轮。
            action = self._parse_tool_action(response)
            if action is None:
                # 普通文本直接输出，并作为 assistant 消息写回上下文。
                print_chunk(response)
                print_chunk("\n")
                self.memory.add("assistant", response)
                return response

            tool_name = action["action"]
            args = action["args"]
            tool = self.tools.get(tool_name)
            if tool is None:
                # 未知工具不抛错，写入工具消息让模型有机会改正。
                self.memory.add("tool", f"Unknown tool: {tool_name}")
                continue

            try:
                # 工具执行失败时把异常信息写回上下文，便于模型根据失败原因重试。
                result = tool.run(args)
            except Exception as exc:
                result = f"Tool {tool_name} failed: {exc}"
            # 先记录模型原始工具请求，再记录工具执行结果，方便后续回看上下文。
            self.memory.add("assistant", response)
            self.memory.add("tool", result)

        # 到达上限后直接结束，避免工具调用循环拖垮交互。
        message = "Tool loop stopped: max_tool_steps reached."
        print_chunk(message)
        print_chunk("\n")
        self.memory.add("assistant", message)
        return message

    def _collect_response(self, print_chunk: Printer) -> str:
        # 收集流式响应时要同时兼顾“边输出边显示”和“判断是否为 JSON 工具调用”。
        chunks: list[str] = []
        should_stream: bool | None = None
        for chunk in self.llm.stream_chat(self._messages_for_llm()):
            chunks.append(chunk)
            if should_stream is None:
                # 先看前导字符，判断这是普通文本还是需要整体解析的 JSON。
                stripped = "".join(chunks).lstrip()
                if not stripped:
                    continue
                should_stream = not stripped.startswith("{")
                if should_stream:
                    # 普通文本可以边收边打印，提升终端响应感。
                    print_chunk("".join(chunks))
                    continue
            elif should_stream:
                print_chunk(chunk)
        # 无论是否流式打印，最终都要返回完整文本供后续解析或入库。
        return "".join(chunks).strip()

    def _messages_for_llm(self) -> list[dict[str, str]]:
        # 每次请求都把工具说明合并进系统提示，方便模型遵守 JSON 协议。
        return self.memory.messages(self._system_prompt_with_tools())

    def _system_prompt_with_tools(self) -> str:
        # 在原始系统提示后追加工具说明和调用规则，尽量让模型稳定地产生结构化输出。
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
        # 工具调用要求模型只返回 JSON；如果解析失败，就把它当作普通文本处理。
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return None

        # 只有最外层是字典，并且包含 action/args 才认定为工具调用。
        if not isinstance(data, dict):
            return None
        action = data.get("action")
        args = data.get("args", {})
        if not isinstance(action, str) or not isinstance(args, dict):
            return None
        return {"action": action, "args": args}
