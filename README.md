# llmbox

本地 LLM 工具箱，提供 CLI 和 Web Chat UI 两种交互方式，连接本地 llama.cpp server，支持流式对话和 prompt-based JSON 工具调用。

## 功能

- CLI 交互模式（终端聊天）
- Web Chat UI（浏览器聊天界面，SSE 流式推送）
- 多轮对话记忆（滑动窗口）
- 工具调用（prompt-based JSON，不依赖 native function calling）
- 运行时配置调整
- 多会话支持（Web 模式）

## 项目要求

- Python 3.12+
- `uv`
- 本地可访问的 `llama.cpp` OpenAI 兼容服务

## 环境准备

```bash
source .venv/bin/activate
uv sync
```

## 启动方式

### CLI 模式

```bash
llmbox
```

### Web 模式

```bash
llmbox serve
```

浏览器访问 `http://localhost:8000`。

### 默认连接配置

- `base_url`: `http://localhost:8080/v1`
- `api_key`: `llama.cpp`
- `model`: `local-model`

## CLI 交互命令

- `/exit`：退出程序
- `/clear`：清空对话记忆
- `/system <文本>`：替换系统提示词
- `/set <key> <value>`：修改运行时配置

支持的配置项：`base_url`、`api_key`、`model`、`temperature`、`max_tokens`、`memory_turns`、`max_tool_steps`

## 工具系统

使用 prompt + JSON 输出方式调用工具。模型需要调用工具时输出：

```json
{"action": "tool_name", "args": {}}
```

内置工具：

- `echo`：计算输入文本的字符数
- `current_time`：返回当前本地时间

## HTTP API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/chat` | POST | 发送消息，返回 SSE 流 |
| `/api/sessions` | GET | 列出会话 |
| `/api/sessions` | POST | 创建新会话 |
| `/api/sessions/{id}` | DELETE | 删除会话 |

### SSE 事件类型

| 事件 | 说明 |
|------|------|
| `text` | 普通文本片段 |
| `tool_call` | 工具调用开始 |
| `tool_result` | 工具返回结果 |
| `done` | 本轮结束 |
| `error` | 错误 |

## 代码结构

```
core/
├── controller.py    # Agent 循环
├── memory.py        # 会话管理
├── tools.py         # 工具注册
└── llm_client.py    # LLM 调用
cli.py               # CLI 前端
server.py            # HTTP 前端（FastAPI + SSE）
web/                 # Web Chat UI 静态文件
main.py              # 入口（llmbox / llmbox serve）
```

## 说明

- 本项目默认面向本地模型服务，不会主动连接公网模型。
- 工具调用失败或模型输出非 JSON 时，按普通文本处理，避免会话中断。
- Web 模式的会话存储在内存中，重启后丢失。
