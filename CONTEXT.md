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

**Scheduler**:
后台调度器，管理倒计时任务（TimerTask）和定时任务（CronTask）。独立线程运行，通过通知回调推送结果。
_Avoid_: 调度引擎, 定时器管理器

**TimerTask**:
一次性倒计时提醒。设定秒数后触发，触发后自动删除。
_Avoid_: 倒计时, 延迟任务

**CronTask**:
周期性 shell 命令执行。按固定间隔重复运行，可手动移除。最近执行结果保留在内存中供查询。
_Avoid_: 定时任务, 周期任务

**AppConfig**:
从 TOML 配置文件加载的全局应用配置，包含 LLM 连接参数（base_url、api_key、model）、Agent 参数（max_tool_steps）、Session 默认值（memory_turns、system_prompt）。搜索顺序：`./llmbox.toml` → `~/.config/llmbox/config.toml`。
_Avoid_: 配置, 设置

**Notification**:
Scheduler 产生的提醒推送。CLI 模式通过 stderr + bell 字符通知；Web 模式通过 SSE `/api/events` 端点推送，前端展示 toast 和浏览器系统通知。
_Avoid_: 提醒, 通知消息

## Relationships

- **llmbox** 包含一个 **Core** 层和两个前端（CLI、HTTP）
- **Core** 包含 **Agent**、**Memory**、**ToolRegistry**、**LLMClient**、**Scheduler**
- **Agent** 在一个 **Turn** 内多次调用 **LLMClient** 和 **Tool**
- **Session** 持有自己的 **Memory** 和配置覆盖
- **SSE Event** 是 HTTP 模式下 **Turn** 过程的实时推送
- **Scheduler** 管理 **TimerTask** 和 **CronTask**，通过 **Notification** 推送结果
- **AppConfig** 提供全局默认值，新建 **Session** 时继承并可覆盖
- **Tool** 分为内置工具（echo、current_time、shell、read_file、write_file）和调度工具（timer_set、timer_list、cron_add、cron_list、cron_remove）

## Example dialogue

> **Dev:** "用户在 Web UI 发送消息后，Agent 的 Turn 是怎么流转的？"
> **Domain expert:** "前端 POST 到 /api/chat，服务端创建 SSE 流，Agent 执行 Turn，每产生一个 SSE Event 就推给前端——文本片段是 text 事件，工具调用是 tool_call + tool_result，最后发 done。"

> **Dev:** "CLI 模式和 Web 模式的 Agent 有什么区别？"
> **Domain expert:** "Agent 本身没区别，都是同一个 Core。区别在前端：CLI 直接 print chunk，Web 通过 SSE 推 event。"

> **Dev:** "工具调用结果在消息历史中是什么角色？"
> **Domain expert:** "为了兼容 llama.cpp 的严格 user/assistant 角色交替，工具调用 JSON 和执行结果都作为 user 消息注入，格式是 `[Tool call: ...]\nResult: ...`。详见 ADR-0004。"

> **Dev:** "定时器触发后通知怎么到达用户？"
> **Domain expert:** "Scheduler 通过构造时传入的 notify 回调推送。CLI 模式写 stderr + bell，Web 模式推入 asyncio 队列，由 `/api/events` SSE 端点消费。详见 ADR-0005。"

> **Dev:** "配置文件怎么加载的？"
> **Domain expert:** "先找当前目录 `./llmbox.toml`，再找 `~/.config/llmbox/config.toml`，都没找到就用内置默认值。CLI 用 `/set` 命令可运行时修改，Web 用 PATCH API。详见 ADR-0006。"

## Flagged ambiguities

- "tool" 在不同语境下可能指 Tool 定义（Tool dataclass）或工具调用的一次执行（tool_call event）—— resolved: Tool 指定义，tool_call 指执行。
