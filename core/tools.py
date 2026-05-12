from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
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


def _run_shell(command: str, timeout: int = 30) -> str:
    """执行 shell 命令，返回 stdout + stderr。"""
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=timeout,
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += ("\n" if output else "") + result.stderr
        if result.returncode != 0:
            output += f"\n[exit code: {result.returncode}]"
        return output.strip() or "[no output]"
    except subprocess.TimeoutExpired:
        return f"[timeout: command exceeded {timeout}s]"
    except Exception as exc:
        return f"[error: {exc}]"


def _read_file(path: str, max_lines: int = 500) -> str:
    """读取文件内容，限制行数防止上下文溢出。"""
    p = Path(path).expanduser()
    if not p.exists():
        return f"[error: file not found: {path}]"
    if not p.is_file():
        return f"[error: not a file: {path}]"
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        if len(lines) > max_lines:
            head = lines[:max_lines]
            head.append(f"\n... ({len(lines) - max_lines} more lines truncated)")
            return "\n".join(head)
        return "\n".join(lines)
    except Exception as exc:
        return f"[error: {exc}]"


def _write_file(path: str, content: str) -> str:
    """写入文件内容，自动创建父目录。"""
    p = Path(path).expanduser()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"wrote {len(content)} chars to {path}"
    except Exception as exc:
        return f"[error: {exc}]"


def build_default_registry(scheduler: Any = None) -> ToolRegistry:
    """默认注册表，提供基础工具。scheduler 可选传入以启用定时任务工具。"""
    registry = ToolRegistry()
    registry.register(
        Tool(
            name="echo",
            description="计算用户输入总共有多少个字符.",
            parameters={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
            handler=lambda text: f"Text length: {len(text)}",
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
    registry.register(
        Tool(
            name="shell",
            description="执行 shell 命令并返回输出。可用于查看目录、运行程序等。",
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "要执行的 shell 命令"},
                },
                "required": ["command"],
            },
            handler=_run_shell,
        )
    )
    registry.register(
        Tool(
            name="read_file",
            description="读取文件内容。返回文件的文本内容，超过 500 行会截断。",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                },
                "required": ["path"],
            },
            handler=_read_file,
        )
    )
    registry.register(
        Tool(
            name="write_file",
            description="写入文件内容。自动创建父目录。会覆盖已有内容。",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                    "content": {"type": "string", "description": "要写入的内容"},
                },
                "required": ["path", "content"],
            },
            handler=_write_file,
        )
    )

    # 定时任务工具（需要 scheduler）
    if scheduler is not None:
        registry.register(
            Tool(
                name="timer_set",
                description="设置倒计时提醒。到时间后会收到通知。",
                parameters={
                    "type": "object",
                    "properties": {
                        "seconds": {"type": "integer", "description": "倒计时秒数"},
                        "message": {"type": "string", "description": "提醒内容"},
                    },
                    "required": ["seconds", "message"],
                },
                handler=lambda seconds, message: f"timer created: {scheduler.set_timer(int(seconds), message)}",
            )
        )
        registry.register(
            Tool(
                name="timer_list",
                description="列出所有倒计时任务。",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=lambda: json.dumps(scheduler.list_timers(), ensure_ascii=False),
            )
        )
        registry.register(
            Tool(
                name="cron_add",
                description="创建定时执行任务。每隔指定秒数执行一次 shell 命令。",
                parameters={
                    "type": "object",
                    "properties": {
                        "interval_seconds": {"type": "integer", "description": "执行间隔（秒）"},
                        "command": {"type": "string", "description": "要执行的 shell 命令"},
                    },
                    "required": ["interval_seconds", "command"],
                },
                handler=lambda interval_seconds, command: f"cron created: {scheduler.add_cron(int(interval_seconds), command)}",
            )
        )
        registry.register(
            Tool(
                name="cron_list",
                description="列出所有定时任务和最近执行结果。",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=lambda: json.dumps(scheduler.list_crons(), ensure_ascii=False, indent=2),
            )
        )
        registry.register(
            Tool(
                name="cron_remove",
                description="取消指定的定时任务。",
                parameters={
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "任务 ID"},
                    },
                    "required": ["id"],
                },
                handler=lambda id: f"removed: {scheduler.remove_cron(id)}",
            )
        )

    return registry
