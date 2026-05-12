# ADR-0002: Prompt-based JSON 工具调用

## 状态

已接受

## 背景

需要让 Agent 具备调用外部工具的能力。有两种主流方案：OpenAI native function calling 和 prompt-based JSON。

## 决策

使用 prompt-based JSON：在 system prompt 中注入工具描述和调用规则，模型输出 `{"action": "tool_name", "args": {...}}` 格式的 JSON，controller 解析并执行。

## 理由

- 兼容任何 OpenAI-compatible API（包括 llama.cpp），不依赖特定 provider 的 function calling 实现
- 实现简单，不需要维护 tool_call_id 等额外状态
- 对小模型更友好——小模型的 function calling 支持往往不稳定，prompt-based 更可靠

## 后果

- 流式输出时需要判断首字符是否为 `{` 来区分工具调用和普通文本，存在误判风险
- 模型可能在 JSON 外包裹 markdown fences，需要容错处理
- 工具参数没有 schema 校验，需要运行时类型检查
