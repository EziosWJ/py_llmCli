from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable


ToolHandler = Callable[..., Any]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler

    def run(self, args: dict[str, Any]) -> str:
        result = self.handler(**args)
        return str(result)

    def prompt_description(self) -> str:
        return (
            f"- {self.name}: {self.description}\n"
            f"  parameters: {self.parameters}"
        )


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def prompt_descriptions(self) -> str:
        if not self._tools:
            return "No tools are available."
        return "\n".join(tool.prompt_description() for tool in self._tools.values())


def build_default_registry() -> ToolRegistry:
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
