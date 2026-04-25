from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

try:
    from openai import OpenAI
except ModuleNotFoundError as exc:
    raise ModuleNotFoundError(
        "The 'openai' package is required. Install project dependencies before running the CLI."
    ) from exc

from memory import Message


@dataclass
class LLMConfig:
    base_url: str = "http://localhost:8080/v1"
    api_key: str = "llama.cpp"
    model: str = "local-model"
    temperature: float = 0.7
    max_tokens: int = 1024


class LLMClient:
    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self._client = OpenAI(base_url=config.base_url, api_key=config.api_key)

    def refresh(self) -> None:
        self._client = OpenAI(base_url=self.config.base_url, api_key=self.config.api_key)

    def stream_chat(self, messages: list[Message]) -> Iterable[str]:
        stream = self._client.chat.completions.create(
            model=self.config.model,
            messages=messages,  # type: ignore[arg-type]
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
