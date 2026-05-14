# ADR-0004: llama.cpp 工具调用角色兼容

## 状态

已接受

## 背景

llama.cpp 的 Chat Template 要求严格的消息角色交替：user → assistant → user → assistant，不允许连续相同角色。当 Agent 执行工具调用时，会产生 assistant（工具调用 JSON）→ tool（工具结果）→ assistant（最终回答）的序列，其中 tool 角色不被 llama.cpp 识别，连续的 assistant 消息也会导致 prompt template 报错 "No user query found in messages"。

## 决策

将工具调用 JSON 和执行结果合并为一条 user 消息注入历史，格式为：

```
[Tool call: {"action": "tool_name", "args": {...}}]
Result: <tool output>
```

这样保持了严格的 user/assistant 交替，不引入 tool 角色。

## 理由

- llama.cpp 的 Jinja template 解析器对角色序列有硬性约束，违反会导致请求失败
- 将工具交互伪装为 user 消息是最简单可靠的兼容方案
- 模型仍能从上下文中理解工具调用和结果的语义

## 后果

- 消息历史中 tool 交互和真实用户输入混在一起，调试时需要区分
- 如果未来切换到支持 native function calling 的 provider，需要回退此方案
- 模型对 `[Tool call: ...]` 格式的理解依赖 prompt 中的工具调用说明
