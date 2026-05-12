from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.controller import AgentConfig
from core.llm_client import LLMConfig
from core.session import GlobalDefaults, SessionConfig, SessionManager


app = FastAPI(title="llmbox", description="本地 LLM 工具箱 API")
manager = SessionManager()


# --- 请求/响应模型 ---

class ChatRequest(BaseModel):
    session_id: str
    message: str


class CreateSessionRequest(BaseModel):
    temperature: float | None = None
    max_tokens: int | None = None
    model: str | None = None
    memory_turns: int | None = None
    max_tool_steps: int | None = None
    system_prompt: str | None = None


class UpdateConfigRequest(BaseModel):
    key: str
    value: str | float | int


# --- SSE 事件格式化 ---

def sse_event(event: str, data: dict | str) -> str:
    """格式化一条 SSE 事件。"""
    if isinstance(data, dict):
        data = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {data}\n\n"


# --- API 端点 ---

@app.post("/api/chat")
async def chat(req: ChatRequest):
    """发送消息，返回 SSE 流。"""
    session = manager.get_session(req.session_id)
    if session is None:
        raise HTTPException(404, f"Session {req.session_id} not found")

    def event_stream():
        try:
            for event in session.controller.run_turn_streaming(req.message):
                yield sse_event(event["type"], event["data"])
        except Exception as exc:
            yield sse_event("error", {"message": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/sessions")
async def list_sessions():
    """列出所有会话。"""
    return {"sessions": manager.list_sessions()}


@app.post("/api/sessions")
async def create_session(req: CreateSessionRequest | None = None):
    """创建新会话。"""
    overrides = SessionConfig(
        temperature=req.temperature if req else None,
        max_tokens=req.max_tokens if req else None,
        model=req.model if req else None,
        memory_turns=req.memory_turns if req else None,
        max_tool_steps=req.max_tool_steps if req else None,
        system_prompt=req.system_prompt if req else None,
    )
    session = manager.create_session(overrides)
    return {"session_id": session.id}


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除会话。"""
    if not manager.delete_session(session_id):
        raise HTTPException(404, f"Session {session_id} not found")
    return {"deleted": True}


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """获取会话详情。"""
    session = manager.get_session(session_id)
    if session is None:
        raise HTTPException(404, f"Session {session_id} not found")
    return {
        "id": session.id,
        "message_count": len(session.memory._messages),
        "config": {
            "temperature": session.llm.config.temperature,
            "max_tokens": session.llm.config.max_tokens,
            "model": session.llm.config.model,
            "memory_turns": session.memory.max_turns,
            "max_tool_steps": session.controller.config.max_tool_steps,
        },
    }


@app.patch("/api/sessions/{session_id}/config")
async def update_session_config(session_id: str, req: UpdateConfigRequest):
    """更新会话配置。"""
    try:
        success = manager.update_session_config(session_id, req.key, req.value)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if not success:
        raise HTTPException(400, f"Unknown config key: {req.key}")
    return {"updated": True}


# --- 静态文件挂载 ---

web_dir = Path(__file__).parent / "web"
if web_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(web_dir), html=True), name="web")
