from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Generator

from core.llm_client import LLMClient
from core.memory import ConversationMemory
from core.tools import ToolRegistry


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
            action = self._parse_tool_action(response) or self._extract_tool_action(response)
            if action is None:
                # 普通文本已经在流式收包阶段输出过了，这里只补换行避免粘连到下一次输入。
                print_chunk("\n")
                self.memory.add("assistant", response)
                return response

            tool_name = action["action"]
            args = action["args"]
            tool = self.tools.get(tool_name)
            if tool is None:
                # 未知工具不抛错，合并到 assistant 消息让模型有机会改正。
                self.memory.add("assistant", f"{response}\n\nResult: Unknown tool: {tool_name}")
                continue

            try:
                result = tool.run(args)
            except Exception as exc:
                result = f"Tool {tool_name} failed: {exc}"
            # 工具调用和结果合并为一条 assistant 消息，避免连续 assistant 角色。
            self.memory.add("assistant", f"{response}\n\nResult: {result}")

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
- If no tool is needed, answer normally in plain text.
- If a tool is needed, return ONLY the raw JSON object, nothing else:
  {{"action": "tool_name", "args": {{"param": "value"}}}}
- Do NOT wrap JSON in markdown fences.
- Do NOT add any text before or after the JSON (no "json", no explanation).
- The response must start with {{ and end with }} when calling a tool.
"""

    def run_turn_streaming(self, user_input: str) -> Generator[dict[str, Any], None, None]:
        """流式执行一轮对话，yield SSE 事件字典供 HTTP 前端消费。"""
        self.memory.add("user", user_input)

        for _ in range(self.config.max_tool_steps + 1):
            # 收集流式响应
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
                    yield {"type": "text", "data": {"content": chunk}}

            response = "".join(chunks).strip()
            # 尝试解析工具调用，支持从文本中提取 JSON
            action = self._parse_tool_action(response) or self._extract_tool_action(response)

            if action is None:
                # 普通文本
                self.memory.add("assistant", response)
                return

            # 工具调用：把模型的 JSON 输出也作为文本展示给用户
            if should_stream is False:
                yield {"type": "text", "data": {"content": response + "\n"}}

            tool_name = action["action"]
            args = action["args"]
            yield {"type": "tool_call", "data": {"tool": tool_name, "args": args}}

            tool = self.tools.get(tool_name)
            if tool is None:
                self.memory.add("assistant", f"{response}\n\nResult: Unknown tool: {tool_name}")
                yield {"type": "tool_result", "data": {"tool": tool_name, "result": f"Unknown tool: {tool_name}"}}
                continue

            try:
                result = tool.run(args)
            except Exception as exc:
                result = f"Tool {tool_name} failed: {exc}"

            # 工具调用和结果合并为一条 assistant 消息，避免连续 assistant 角色。
            self.memory.add("assistant", f"{response}\n\nResult: {result}")
            yield {"type": "tool_result", "data": {"tool": tool_name, "result": result}}

        # 工具调用次数超限
        message = "Tool loop stopped: max_tool_steps reached."
        self.memory.add("assistant", message)
        yield {"type": "text", "data": {"content": message}}

    @staticmethod
    def _parse_tool_action(text: str) -> dict[str, object] | None:
        """尝试将整个文本解析为工具调用 JSON。"""
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

    @staticmethod
    def _extract_tool_action(text: str) -> dict[str, object] | None:
        """从文本中提取 JSON 工具调用（处理模型输出带前缀/后缀的情况）。"""
        # 去掉 markdown 代码块包裹
        import re
        cleaned = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
        if cleaned != text.strip():
            action = AgentController._parse_tool_action(cleaned)
            if action is not None:
                return action

        # 尝试提取第一个 JSON 对象
        start = text.find("{")
        if start == -1:
            return None
        # 从右往找最后一个 }
        end = text.rfind("}")
        if end <= start:
            return None
        candidate = text[start:end + 1]
        return AgentController._parse_tool_action(candidate)
