from __future__ import annotations

from dataclasses import dataclass, field


Message = dict[str, str]


@dataclass
class ConversationMemory:
    # system_prompt 单独保存，方便随时覆盖，而不是混进普通消息列表里。
    system_prompt: str
    max_turns: int = 10
    _messages: list[Message] = field(default_factory=list)

    def add(self, role: str, content: str) -> None:
        # 统一使用 OpenAI 兼容的消息结构，便于直接送入聊天接口。
        self._messages.append({"role": role, "content": content})
        self._trim()

    def clear(self) -> None:
        # 清空对话历史，但保留系统提示，避免上下文策略丢失。
        self._messages.clear()

    def set_system_prompt(self, prompt: str) -> None:
        # 系统提示可在运行时替换，用于动态调整模型行为。
        self.system_prompt = prompt

    def set_max_turns(self, turns: int) -> None:
        # 至少保留一轮消息，防止配置成 0 后完全没有上下文。
        if turns < 1:
            raise ValueError("memory_turns must be at least 1")
        self.max_turns = turns
        self._trim()

    def messages(self, system_prompt: str | None = None) -> list[Message]:
        # 每次请求都把系统消息放在最前面，其余历史消息按时间顺序拼接。
        prompt = system_prompt if system_prompt is not None else self.system_prompt
        return [{"role": "system", "content": prompt}, *self._messages]

    def _trim(self) -> None:
        # 只保留最近的 max_turns 轮，每轮按 user + assistant 计算两条消息。
        max_messages = self.max_turns * 2
        if len(self._messages) > max_messages:
            self._messages = self._messages[-max_messages:]
