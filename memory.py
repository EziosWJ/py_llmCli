from __future__ import annotations

from dataclasses import dataclass, field


Message = dict[str, str]


@dataclass
class ConversationMemory:
    system_prompt: str
    max_turns: int = 10
    _messages: list[Message] = field(default_factory=list)

    def add(self, role: str, content: str) -> None:
        self._messages.append({"role": role, "content": content})
        self._trim()

    def clear(self) -> None:
        self._messages.clear()

    def set_system_prompt(self, prompt: str) -> None:
        self.system_prompt = prompt

    def set_max_turns(self, turns: int) -> None:
        if turns < 1:
            raise ValueError("memory_turns must be at least 1")
        self.max_turns = turns
        self._trim()

    def messages(self, system_prompt: str | None = None) -> list[Message]:
        prompt = system_prompt if system_prompt is not None else self.system_prompt
        return [{"role": "system", "content": prompt}, *self._messages]

    def _trim(self) -> None:
        max_messages = self.max_turns * 2
        if len(self._messages) > max_messages:
            self._messages = self._messages[-max_messages:]
