from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from core.controller import AgentConfig, AgentController
from core.llm_client import LLMClient, LLMConfig
from core.memory import ConversationMemory
from core.tools import ToolRegistry, build_default_registry


DEFAULT_SYSTEM_PROMPT = "You are a helpful local CLI assistant."


@dataclass
class SessionConfig:
    """单个会话的配置覆盖项。None 表示使用全局默认值。"""
    temperature: float | None = None
    max_tokens: int | None = None
    model: str | None = None
    memory_turns: int | None = None
    max_tool_steps: int | None = None
    system_prompt: str | None = None


@dataclass
class Session:
    """一个独立的对话会话，包含自己的 memory、controller 和配置。"""
    id: str
    memory: ConversationMemory
    llm: LLMClient
    controller: AgentController
    config_overrides: SessionConfig = field(default_factory=SessionConfig)


@dataclass
class GlobalDefaults:
    """全局默认配置，新建会话时继承。"""
    llm: LLMConfig = field(default_factory=LLMConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    memory_turns: int = 10
    system_prompt: str = DEFAULT_SYSTEM_PROMPT


class SessionManager:
    """管理多个独立会话。"""

    def __init__(
        self,
        defaults: GlobalDefaults | None = None,
        tools: ToolRegistry | None = None,
    ) -> None:
        self.defaults = defaults or GlobalDefaults()
        self.tools = tools or build_default_registry()
        self._sessions: dict[str, Session] = {}

    def create_session(self, overrides: SessionConfig | None = None) -> Session:
        """创建新会话，继承全局默认值并应用配置覆盖。"""
        sid = uuid.uuid4().hex[:12]
        overrides = overrides or SessionConfig()

        # 合并配置：覆盖项优先，否则用全局默认
        llm_config = LLMConfig(
            base_url=self.defaults.llm.base_url,
            api_key=self.defaults.llm.api_key,
            model=overrides.model or self.defaults.llm.model,
            temperature=overrides.temperature if overrides.temperature is not None else self.defaults.llm.temperature,
            max_tokens=overrides.max_tokens if overrides.max_tokens is not None else self.defaults.llm.max_tokens,
        )
        memory_turns = overrides.memory_turns or self.defaults.memory_turns
        max_tool_steps = overrides.max_tool_steps if overrides.max_tool_steps is not None else self.defaults.agent.max_tool_steps
        system_prompt = overrides.system_prompt or self.defaults.system_prompt

        llm = LLMClient(llm_config)
        memory = ConversationMemory(system_prompt, max_turns=memory_turns)
        controller = AgentController(
            llm=llm,
            memory=memory,
            tools=self.tools,
            config=AgentConfig(max_tool_steps=max_tool_steps),
        )

        session = Session(
            id=sid,
            memory=memory,
            llm=llm,
            controller=controller,
            config_overrides=overrides,
        )
        self._sessions[sid] = session
        return session

    def get_session(self, session_id: str) -> Session | None:
        """获取指定会话，不存在返回 None。"""
        return self._sessions.get(session_id)

    def delete_session(self, session_id: str) -> bool:
        """删除会话，返回是否成功。"""
        return self._sessions.pop(session_id, None) is not None

    def list_sessions(self) -> list[dict[str, Any]]:
        """列出所有会话的基本信息。"""
        return [
            {"id": s.id, "message_count": len(s.memory._messages)}
            for s in self._sessions.values()
        ]

    def update_session_config(self, session_id: str, key: str, value: Any) -> bool:
        """更新会话的运行时配置。"""
        session = self.get_session(session_id)
        if session is None:
            return False

        if key == "temperature":
            if value < 0:
                raise ValueError("temperature must be non-negative")
            session.llm.config.temperature = value
            session.config_overrides.temperature = value
        elif key == "max_tokens":
            if value < 1:
                raise ValueError("max_tokens must be at least 1")
            session.llm.config.max_tokens = value
            session.config_overrides.max_tokens = value
        elif key == "model":
            session.llm.config.model = value
            session.config_overrides.model = value
        elif key == "memory_turns":
            session.memory.set_max_turns(value)
            session.config_overrides.memory_turns = value
        elif key == "max_tool_steps":
            if value < 0:
                raise ValueError("max_tool_steps must be at least 0")
            session.controller.config.max_tool_steps = value
            session.config_overrides.max_tool_steps = value
        elif key == "base_url":
            session.llm.config.base_url = value
            session.llm.refresh()
        elif key == "api_key":
            session.llm.config.api_key = value
            session.llm.refresh()
        else:
            return False
        return True
