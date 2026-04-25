# py-llmcli

A minimal terminal chat agent for a local llama.cpp OpenAI-compatible server.

## Setup

Install the project dependency:

```bash
python3 -m pip install -e .
```

Start llama.cpp server separately, then run:

```bash
python3 main.py
```

Defaults:

- `base_url`: `http://localhost:8080/v1`
- `api_key`: `llama.cpp`
- `model`: `local-model`

## CLI Commands

- `/exit` quits the session.
- `/clear` clears conversation memory.
- `/system <text>` replaces the system prompt.
- `/set <key> <value>` updates runtime config.

Supported config keys: `base_url`, `api_key`, `model`, `temperature`, `max_tokens`, `memory_turns`, `max_tool_steps`.

## Tools

Tool calls are prompt-based JSON, not native function calling. The first version includes safe example tools:

- `echo`
- `current_time`
