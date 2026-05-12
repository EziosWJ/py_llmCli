from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from core.llm_client import LLMConfig


# 配置文件搜索路径（按优先级）
_CONFIG_SEARCH_PATHS = [
    Path("llmbox.toml"),                    # 项目目录
    Path.home() / ".config" / "llmbox" / "config.toml",  # 用户全局配置
]

_DEFAULT_CONFIG = """\
[llm]
base_url = "http://localhost:8000/v1"
api_key = "llama.cpp"
model = "local-model"
temperature = 0.7
max_tokens = 1024

[agent]
max_tool_steps = 3

[session]
memory_turns = 10
system_prompt = "You are a helpful local CLI assistant."
"""


@dataclass
class AppConfig:
    """应用完整配置。"""
    llm: LLMConfig = field(default_factory=LLMConfig)
    max_tool_steps: int = 3
    memory_turns: int = 10
    system_prompt: str = "You are a helpful local CLI assistant."


def find_config_file() -> Path | None:
    """查找已存在的配置文件，返回第一个匹配的路径。"""
    for path in _CONFIG_SEARCH_PATHS:
        if path.is_file():
            return path
    return None


def load_config(config_path: Path | None = None) -> AppConfig:
    """从配置文件加载配置，未找到则使用默认值。"""
    if config_path is None:
        config_path = find_config_file()

    if config_path is None or not config_path.is_file():
        return AppConfig()

    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    llm_section = data.get("llm", {})
    agent_section = data.get("agent", {})
    session_section = data.get("session", {})

    llm_config = LLMConfig(
        base_url=llm_section.get("base_url", LLMConfig.base_url),
        api_key=llm_section.get("api_key", LLMConfig.api_key),
        model=llm_section.get("model", LLMConfig.model),
        temperature=llm_section.get("temperature", LLMConfig.temperature),
        max_tokens=llm_section.get("max_tokens", LLMConfig.max_tokens),
    )

    return AppConfig(
        llm=llm_config,
        max_tool_steps=agent_section.get("max_tool_steps", 3),
        memory_turns=session_section.get("memory_turns", 10),
        system_prompt=session_section.get("system_prompt", AppConfig.system_prompt),
    )


def create_default_config(path: Path) -> None:
    """在指定路径创建默认配置文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_DEFAULT_CONFIG, encoding="utf-8")
