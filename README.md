# py-llmcli

一个面向本地 `llama.cpp` OpenAI 兼容服务的终端聊天代理。

它支持：

- 流式输出
- 多轮对话记忆
- 基于 JSON 的提示词工具调用
- 运行时配置调整

## 项目要求

- Python 3.12+
- `uv`
- 本地可访问的 `llama.cpp` OpenAI 兼容服务

## 环境准备

项目约定使用虚拟环境 `.venv`。如果你已经有这个环境，可以直接激活后继续操作：

```bash
source .venv/bin/activate
```

如果还没有安装依赖，使用 `uv` 同步当前项目依赖：

```bash
source .venv/bin/activate
uv sync
```

如果你需要手动补装依赖，也可以使用：

```bash
source .venv/bin/activate
uv add openai
```

## 启动方式

先启动你的本地 `llama.cpp` 服务，再运行程序：

```bash
source .venv/bin/activate
python main.py
```

如果你的环境已经正确安装了项目脚本，也可以尝试：

```bash
source .venv/bin/activate
uv run llmcli
```

默认连接配置如下：

- `base_url`: `http://localhost:8080/v1`
- `api_key`: `llama.cpp`
- `model`: `local-model`

## 交互命令

在终端中输入以下命令可以控制会话：

- `/exit`：退出程序
- `/clear`：清空对话记忆
- `/system <文本>`：替换系统提示词
- `/set <key> <value>`：修改运行时配置

支持的配置项：

- `base_url`
- `api_key`
- `model`
- `temperature`
- `max_tokens`
- `memory_turns`
- `max_tool_steps`

示例：

```bash
/set temperature 0.2
/set max_tokens 512
/set memory_turns 20
```

## 工具系统

当前版本使用“提示词 + JSON 输出”的方式让模型调用工具，不依赖原生 function calling。

内置示例工具：

- `echo`：原样返回输入文本
- `current_time`：返回当前本地时间

模型需要调用工具时，应该只输出如下格式的 JSON：

```json
{
  "action": "tool_name",
  "args": {}
}
```

如果不需要工具，模型应直接输出正常文本。

## 代码结构

- `cli.py`：终端交互入口
- `controller.py`：对话回合控制与工具循环
- `llm_client.py`：OpenAI 兼容接口封装
- `memory.py`：对话记忆管理
- `tools.py`：工具注册与内置工具
- `main.py`：独立启动入口

## 运行验证

你可以用以下命令做基本检查：

```bash
source .venv/bin/activate
uv run python -m compileall .
```

如果你想做一次最小启动验证：

```bash
source .venv/bin/activate
printf '/exit\n' | uv run python main.py
```

## 说明

- 本项目默认面向本地模型服务，不会主动连接公网模型。
- 如果 `openai` 包没有安装，启动时会提示缺少依赖。
- 工具调用失败或模型输出非 JSON 时，程序会按普通文本处理，避免会话直接中断。
