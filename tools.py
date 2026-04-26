from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable


ToolHandler = Callable[..., Any]


@dataclass(frozen=True)
class Tool:
    # Tool 结构尽量保持简单：元信息 + 处理函数，方便注册和扩展。
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler

    def run(self, args: dict[str, Any]) -> str:
        # 统一把工具返回值转成字符串，便于作为 tool 消息写回上下文。
        result = self.handler(**args)
        return str(result)

    def prompt_description(self) -> str:
        # 把工具信息整理成适合塞进系统提示的纯文本。
        return (
            f"- {self.name}: {self.description}\n"
            f"  parameters: {self.parameters}"
        )


class ToolRegistry:
    def __init__(self) -> None:
        # 使用字典按名称检索工具，避免每次都线性扫描。
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        # 同名工具后注册的会覆盖前者，便于做默认值替换。
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        # 找不到工具时返回 None，由控制器决定是否忽略或报错。
        return self._tools.get(name)

    def prompt_descriptions(self) -> str:
        # 系统提示里只需要工具摘要，不需要暴露内部实现细节。
        if not self._tools:
            return "No tools are available."
        return "\n".join(tool.prompt_description() for tool in self._tools.values())


def build_default_registry() -> ToolRegistry:
    # 默认注册表提供最基础的示例工具，便于验证工具调用链路。
    registry = ToolRegistry()
    registry.register(
        Tool(
            name="echo",
            description="Return the provided text unchanged.",
            parameters={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
            handler=lambda text: text,
        )
    )
    registry.register(
        Tool(
            name="current_time",
            description="Return the current local date and time in ISO 8601 format.",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=lambda: datetime.now().isoformat(timespec="seconds"),
        )
    )
    return registry
