# Task: Build Local LLM CLI Agent (Python)

## Goal

Implement a terminal-based chat agent with:

* Streaming output
* Multi-turn memory
* Tool calling via JSON (prompt-based, NOT native function calling)

---

## Tech

* Python
* llama.cpp server (OpenAI-compatible API)
* Model: Qwen GGUF (Q4)

---

## Requirements

### 1. CLI Loop

* Read user input
* Support commands:

  * /exit → quit
  * /clear → reset memory
  * /set <key> <value> → update config
  * /system <text> → set system prompt

---

### 2. Memory

* Maintain message list:

  * {role: user/assistant/system/tool, content: str}
* Keep last N turns (configurable)

---

### 3. LLM Client

* Call `/v1/chat/completions`
* Support streaming
* Config:

  * temperature
  * max_tokens

---

### 4. Tool System

#### Tool structure

* name
* description
* parameters (JSON schema)
* handler (function)

#### Tool registry

* store tools in dict[name → tool]

---

### 5. Tool Calling (IMPORTANT)

Use prompt to force JSON output:

Expected format:

```json id="f7yuvy"
{
  "action": "tool_name",
  "args": { ... }
}
```

Rules:

* If no tool needed → return normal text
* If tool needed → return ONLY JSON

---

### 6. Agent Loop

```id="3l4sfa"
loop:
  send messages + tool descriptions to LLM
  get response

  if valid JSON with "action":
      find tool
      execute tool(args)
      append tool result as role="tool"
      continue loop
  else:
      print response
      break
```

---

### 7. Error Handling

* JSON parse failure → treat as normal text
* Unknown tool → ignore or fallback
* Prevent infinite loop (max steps)

---

### 8. Prompt Design

System prompt must include:

* tool list
* JSON format instruction
* strict rule: no extra text when calling tool

---

## Output

Produce clean modular code with:

* cli.py
* controller.py
* llm_client.py
* memory.py
* tools.py

Keep code minimal but extensible.
