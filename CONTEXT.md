# llmbox

本地 LLM 工具箱，提供 CLI 和 Web Chat UI 两种交互方式，通过 prompt-based JSON 实现工具调用，连接本地 llama.cpp server。

## Language

**Agent**:
对话循环的核心引擎，负责调用 LLM、解析工具调用、执行工具、返回结果。
_Avoid_: 聊天机器人, bot, assistant

**Tool**:
Agent 可调用的外部能力，通过 JSON schema 描述参数，由 handler 函数执行。
_Avoid_: 函数, function, 插件

**Turn**:
一次用户输入到 Agent 最终回答的完整过程，可能包含多次 LLM 调用和工具调用。
_Avoid_: 轮次, 回合

**Session**:
一个独立的对话上下文，包含自己的 memory、配置覆盖。CLI 模式只有一个 session，Web 模式支持多个。
_Avoid_: 会话（在代码中直接用 session）

**Memory**:
Session 内的消息历史缓冲区，滑动窗口维护最近 N 轮对话。
_Avoid_: 历史记录, 上下文

**Core**:
Agent、Memory、Tool、LLM Client 的共享层，CLI 和 HTTP 两种前端都调用它。
_Aavoid_: 核心, 引擎

**SSE Event**:
HTTP 模式下服务端推送给前端的事件流，类型包括 text、tool_call、tool_result、done、error。
_Avoid_: 消息, 推送

## Relationships

- **llmbox** 包含一个 **Core** 层和两个前端（CLI、HTTP）
- **Core** 包含 **Agent**、**Memory**、**ToolRegistry**、**LLMClient**
- **Agent** 在一个 **Turn** 内多次调用 **LLMClient** 和 **Tool**
- **Session** 持有自己的 **Memory** 和配置覆盖
- **SSE Event** 是 HTTP 模式下 **Turn** 过程的实时推送

## Example dialogue

> **Dev:** "用户在 Web UI 发送消息后，Agent 的 Turn 是怎么流转的？"
> **Domain expert:** "前端 POST 到 /api/chat，服务端创建 SSE 流，Agent 执行 Turn，每产生一个 SSE Event 就推给前端——文本片段是 text 事件，工具调用是 tool_call + tool_result，最后发 done。"

> **Dev:** "CLI 模式和 Web 模式的 Agent 有什么区别？"
> **Domain expert:** "Agent 本身没区别，都是同一个 Core。区别在前端：CLI 直接 print chunk，Web 通过 SSE 推 event。"

## Flagged ambiguities

- "tool" 在不同语境下可能指 Tool 定义（Tool dataclass）或工具调用的一次执行（tool_call event）—— resolved: Tool 指定义，tool_call 指执行。
