from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from controller import AgentConfig, AgentController
from llm_client import LLMClient, LLMConfig
from memory import ConversationMemory
from tools import build_default_registry


DEFAULT_SYSTEM_PROMPT = "You are a helpful local CLI assistant."


@dataclass
class CLIConfig:
    llm: LLMConfig
    memory_turns: int = 10
    max_tool_steps: int = 3


def main() -> None:
    config = CLIConfig(llm=LLMConfig())
    memory = ConversationMemory(DEFAULT_SYSTEM_PROMPT, max_turns=config.memory_turns)
    llm = LLMClient(config.llm)
    controller = AgentController(
        llm=llm,
        memory=memory,
        tools=build_default_registry(),
        config=AgentConfig(max_tool_steps=config.max_tool_steps),
    )

    print("Local LLM CLI. Type /exit to quit.")
    while True:
        try:
            user_input = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue
        if user_input == "/exit":
            break
        if user_input == "/clear":
            memory.clear()
            print("Memory cleared.")
            continue
        if user_input.startswith("/system "):
            memory.set_system_prompt(user_input.removeprefix("/system ").strip())
            print("System prompt updated.")
            continue
        if user_input.startswith("/set "):
            _handle_set(user_input, config, memory, llm, controller)
            continue

        try:
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
    parts = command.split(maxsplit=2)
    if len(parts) != 3:
        print("Usage: /set <key> <value>")
        return

    _, key, raw_value = parts
    try:
        value = _coerce_value(key, raw_value)
        _set_config_value(key, value, config, memory, llm, controller)
    except ValueError as exc:
        print(f"Invalid value: {exc}")
        return

    print(f"{key} set to {raw_value}")


def _coerce_value(key: str, value: str) -> Any:
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
    if key == "memory_turns":
        memory.set_max_turns(value)
        config.memory_turns = value
        return
    if key == "max_tool_steps":
        if value < 0:
            raise ValueError("max_tool_steps must be at least 0")
        controller.config.max_tool_steps = value
        config.max_tool_steps = value
        return

    if key == "temperature":
        if value < 0:
            raise ValueError("temperature must be non-negative")
    if key == "max_tokens" and value < 1:
        raise ValueError("max_tokens must be at least 1")

    setattr(config.llm, key, value)
    if key in {"base_url", "api_key"}:
        llm.refresh()


if __name__ == "__main__":
    main()
