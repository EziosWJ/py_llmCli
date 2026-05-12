from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

try:
    from openai import OpenAI
except ModuleNotFoundError as exc:
    # 依赖缺失时给出明确提示，避免用户直接看到难懂的导入异常。
    raise ModuleNotFoundError(
        "The 'openai' package is required. Install project dependencies before running the CLI."
    ) from exc

from core.memory import Message


@dataclass
class LLMConfig:
    # 默认指向本地 llama.cpp OpenAI 兼容服务，便于开箱即用。
    base_url: str = "http://localhost:8000/v1"
    api_key: str = "llama.cpp"
    model: str = "local-model"
    temperature: float = 0.7
    max_tokens: int = 1024


class LLMClient:
    def __init__(self, config: LLMConfig) -> None:
        # 客户端初始化时直接读取配置，后续通过 refresh 重新绑定。
        self.config = config
        self._client = OpenAI(base_url=config.base_url, api_key=config.api_key)

    def refresh(self) -> None:
        # base_url 或 api_key 变化后，重新创建底层客户端实例。
        self._client = OpenAI(base_url=self.config.base_url, api_key=self.config.api_key)

    def stream_chat(self, messages: list[Message]) -> Iterable[str]:
        # 使用 stream=True 让模型输出尽早回到终端，提升交互速度。
        stream = self._client.chat.completions.create(
            model=self.config.model,
            messages=messages,  # type: ignore[arg-type]
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            stream=True,
        )
        for chunk in stream:
            # OpenAI 流式返回按增量片段传输，只把真正有内容的片段交给上层。
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
