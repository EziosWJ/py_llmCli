from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.config import load_config
from core.controller import AgentConfig, AgentController
from core.llm_client import LLMClient, LLMConfig
from core.memory import ConversationMemory
from core.tools import build_default_registry


@dataclass
class CLIConfig:
    # 运行时配置只保留最常用的几项，方便通过 /set 在交互过程中动态调整。
    llm: LLMConfig
    memory_turns: int = 10
    max_tool_steps: int = 3


def main() -> None:
    # 从配置文件加载默认值，未找到则使用内置默认值。
    app_config = load_config()
    config = CLIConfig(
        llm=app_config.llm,
        memory_turns=app_config.memory_turns,
        max_tool_steps=app_config.max_tool_steps,
    )
    # 对话记忆从默认系统提示开始，并保留最近若干轮上下文。
    memory = ConversationMemory(app_config.system_prompt, max_turns=config.memory_turns)
    # LLM 客户端保存模型连接参数，后续通过 /set 可以动态修改。
    llm = LLMClient(config.llm)
    # 控制器负责一次用户输入到模型输出/工具调用的完整回合。
    controller = AgentController(
        llm=llm,
        memory=memory,
        tools=build_default_registry(),
        config=AgentConfig(max_tool_steps=config.max_tool_steps),
    )

    print("Local LLM CLI. Type /exit to quit.")
    while True:
        try:
            # 逐行读取用户输入；支持 Ctrl+D 和 Ctrl+C 直接结束会话。
            user_input = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        # 空行不触发任何动作，避免污染上下文。
        if not user_input:
            continue
        # 退出命令优先处理，避免进入后续业务流程。
        if user_input == "/exit":
            break
        if user_input == "/clear":
            # 清空历史消息，但保留当前系统提示。
            memory.clear()
            print("Memory cleared.")
            continue
        if user_input.startswith("/system "):
            # 系统提示用于约束模型行为，单独更新，不影响上下文消息列表。
            memory.set_system_prompt(user_input.removeprefix("/system ").strip())
            print("System prompt updated.")
            continue
        if user_input.startswith("/set "):
            # /set 用于在运行时调整模型、记忆和工具循环相关参数。
            _handle_set(user_input, config, memory, llm, controller)
            continue

        try:
            # 普通输入交给控制器处理，输出边生成边打印到终端。
            controller.run_turn(user_input, print_chunk=lambda chunk: print(chunk, end="", flush=True))
        except Exception as exc:
            print(f"Error: {exc}")


def _handle_set(
    command: str,
    config: CLIConfig,
    memory: ConversationMemory,
    llm: LLMClient,
    controller: AgentController,
) -> None:
    # 这里允许用户输入带空格的值，因此最多只拆成三段。
    parts = command.split(maxsplit=2)
    if len(parts) != 3:
        print("Usage: /set <key> <value>")
        return

    _, key, raw_value = parts
    try:
        # 先把字符串转换成目标类型，再统一走配置更新逻辑。
        value = _coerce_value(key, raw_value)
        _set_config_value(key, value, config, memory, llm, controller)
    except ValueError as exc:
        print(f"Invalid value: {exc}")
        return

    print(f"{key} set to {raw_value}")


def _coerce_value(key: str, value: str) -> Any:
    # 这里集中做字符串到具体类型的转换，避免配置更新函数里充斥解析逻辑。
    if key == "temperature":
        return float(value)
    if key in {"max_tokens", "memory_turns", "max_tool_steps"}:
        return int(value)
    if key in {"base_url", "api_key", "model"}:
        return value
    raise ValueError(f"unknown key {key}")


def _set_config_value(
    key: str,
    value: Any,
    config: CLIConfig,
    memory: ConversationMemory,
    llm: LLMClient,
    controller: AgentController,
) -> None:
    # 记忆轮数直接作用于上下文截断策略。
    if key == "memory_turns":
        memory.set_max_turns(value)
        config.memory_turns = value
        return
    # 工具循环步数用于防止模型反复请求工具导致死循环。
    if key == "max_tool_steps":
        if value < 0:
            raise ValueError("max_tool_steps must be at least 0")
        controller.config.max_tool_steps = value
        config.max_tool_steps = value
        return

    # 这些数值参数做基本边界校验，避免把客户端配置成无效状态。
    if key == "temperature":
        if value < 0:
            raise ValueError("temperature must be non-negative")
    if key == "max_tokens" and value < 1:
        raise ValueError("max_tokens must be at least 1")

    # base_url、api_key、model 统一写回 LLM 配置对象。
    setattr(config.llm, key, value)
    if key in {"base_url", "api_key"}:
        # 连接信息变化后重新初始化底层客户端，确保后续请求使用新配置。
        llm.refresh()


if __name__ == "__main__":
    main()
