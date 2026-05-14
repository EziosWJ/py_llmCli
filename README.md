# llmbox

本地 LLM 工具箱，提供 CLI 和 Web Chat UI 两种交互方式，连接本地 llama.cpp server，支持流式对话和 prompt-based JSON 工具调用。

## 功能

- CLI 交互模式（终端聊天）
- Web Chat UI（浏览器聊天界面，SSE 流式推送）
- 多轮对话记忆（滑动窗口）
- 工具调用（prompt-based JSON，不依赖 native function calling）
- 内置实用工具：shell 命令执行、文件读写、定时器、周期任务
- 后台调度器，支持倒计时提醒和定时 shell 命令
- TOML 配置文件，零配置也能运行
- 运行时配置调整（CLI `/set` / Web PATCH API）
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
llmbox serve --host 0.0.0.0 --port 8000
```

参数均可省略，默认 `127.0.0.1:8000`。浏览器访问 `http://localhost:8000`。

### 生成配置文件

```bash
llmbox init
```

在当前目录生成 `llmbox.toml` 模板。

## 配置文件

配置文件为 TOML 格式，搜索顺序：

1. `./llmbox.toml`（项目级）
2. `~/.config/llmbox/config.toml`（用户级）
3. 未找到则使用内置默认值

```toml
[llm]
base_url = "http://localhost:8080/v1"
api_key  = "llama.cpp"
model    = "local-model"
temperature = 0.7
max_tokens  = 2048

[agent]
max_tool_steps = 3

[session]
memory_turns  = 10
system_prompt = "You are a helpful local CLI assistant."
```

## CLI 交互命令

- `/exit`：退出程序
- `/clear`：清空对话记忆
- `/system <文本>`：替换系统提示词
- `/set <key> <value>`：修改运行时配置

支持的配置项：`base_url`、`api_key`、`model`、`temperature`、`max_tokens`、`memory_turns`、`max_tool_steps`

## 工具系统

使用 prompt + JSON 输出方式调用工具。模型需要调用工具时输出：

```json
{"action": "tool_name", "args": {"param": "value"}}
```

### 内置工具

| 工具 | 说明 |
|------|------|
| `echo` | 计算输入文本的字符数 |
| `current_time` | 返回当前本地时间（ISO 8601） |
| `shell` | 执行 shell 命令并返回输出（默认 30s 超时） |
| `read_file` | 读取文件内容（超过 500 行截断） |
| `write_file` | 写入文件，自动创建父目录 |

### 调度工具

| 工具 | 说明 |
|------|------|
| `timer_set` | 设置倒计时提醒（秒），到期后推送通知 |
| `timer_list` | 列出所有倒计时任务 |
| `cron_add` | 创建周期性 shell 命令（间隔秒数） |
| `cron_list` | 列出所有定时任务和最近执行结果 |
| `cron_remove` | 取消指定的定时任务（传入任务 ID） |

### 通知方式

- CLI 模式：stderr 输出 + bell 字符
- Web 模式：SSE `/api/events` 推送 + 浏览器系统通知

## HTTP API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/chat` | POST | 发送消息，返回 SSE 流 |
| `/api/sessions` | GET | 列出所有会话 |
| `/api/sessions` | POST | 创建新会话（可传配置覆盖） |
| `/api/sessions/{id}` | GET | 获取会话详情 |
| `/api/sessions/{id}` | DELETE | 删除会话 |
| `/api/sessions/{id}/config` | PATCH | 更新会话运行时配置 |
| `/api/events` | GET | SSE 长连接，推送定时任务通知 |

### SSE 事件类型

| 事件 | 说明 |
|------|------|
| `text` | 普通文本片段 |
| `tool_call` | 工具调用开始 |
| `tool_result` | 工具返回结果 |
| `done` | 本轮结束 |
| `error` | 错误 |
| `notification` | 定时任务通知 |

## 代码结构

```
core/
├── controller.py    # Agent 循环（run_turn / run_turn_streaming）
├── memory.py        # 对话记忆（滑动窗口）
├── tools.py         # 工具注册 + 内置工具实现
├── llm_client.py    # OpenAI SDK 封装
├── scheduler.py     # 后台调度器（Timer + Cron）
├── config.py        # TOML 配置文件加载
└── session.py       # 多会话管理
cli.py               # CLI 前端
server.py            # HTTP 前端（FastAPI + SSE）
web/                 # Web Chat UI 静态文件
main.py              # 入口（llmbox / llmbox serve / llmbox init）
```

## 说明

- 本项目默认面向本地模型服务，不会主动连接公网模型。
- 工具调用失败或模型输出非 JSON 时，按普通文本处理，避免会话中断。
- Web 模式的会话存储在内存中，重启后丢失。
- 定时任务同样存储在内存中，重启后清除。
- 为兼容 llama.cpp 的消息角色限制，工具调用结果以 user 消息注入上下文。
