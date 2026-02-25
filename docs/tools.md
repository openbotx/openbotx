# Tools Reference

OpenBotX is an AI assistant platform. Tools are Python functions the AI agent can call during conversations. This document provides a complete reference for all built-in tools, their parameters, and access rules.

## Overview

All tools are registered in `openbotx/tools/`. The `ToolRegistry` manages them and generates OpenAI-compatible function definitions for the LLM. Tools are registered during agent initialization in `AgentLoop._register_tools()`.

The registry:

1. Stores tool instances.
2. Generates OpenAI-compatible function definitions (sent to the LLM).
3. Executes tool calls by name with arguments.
4. Returns string results back to the agent loop.

---

## Built-in Tools

### File Operations

**Source:** `openbotx/tools/filesystem.py`

All file tools respect the `restrict_to_workspace` setting. When enabled, operations are sandboxed to the workspace directory.

#### read_file

Read the contents of a file.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `path` | string | Yes | File path, relative to workspace. |

#### write_file

Create or overwrite a file.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `path` | string | Yes | File path, relative to workspace. |
| `content` | string | Yes | The content to write. |

#### edit_file

Search and replace within a file.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `path` | string | Yes | File path, relative to workspace. |
| `old_text` | string | Yes | The text to find. |
| `new_text` | string | Yes | The replacement text. |

#### list_dir

List the contents of a directory.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `path` | string | No | Directory path, relative to workspace. Defaults to workspace root. |

---

### Shell

**Source:** `openbotx/tools/shell.py`

#### exec

Execute a shell command.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `command` | string | Yes | The shell command to execute. |

The command runs with a configurable timeout (default 60 seconds). When `restrict_to_workspace` is enabled, the working directory is locked to the workspace.

---

### Web

**Source:** `openbotx/tools/web.py`

#### web_search

Search the web using the Brave Search API.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | The search query. |

Requires the `BRAVE_API_KEY` environment variable to be set.

#### web_fetch

Fetch and extract content from a URL.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `url` | string | Yes | The URL to fetch. |

Uses `readability-lxml` for content extraction.

---

### Communication

**Source:** `openbotx/tools/message.py`

#### message

Send a message to the user via the current channel.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `content` | string | Yes | The message content. |

Only available to the main agent (not subagents).

---

### Background Tasks

**Source:** `openbotx/tools/spawn.py`

#### spawn

Launch a subagent for independent background tasks.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `task` | string | Yes | Description of the task for the subagent. |
| `context` | string | Yes | Additional context for the subagent. |

Only available to the main agent. Creates a child task on the task board.

---

### Scheduling

**Source:** `openbotx/tools/cron.py`

#### cron

Schedule reminders and recurring tasks.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `action` | string | Yes | One of `add`, `list`, or `remove`. |
| `name` | string | Yes | Unique name for the scheduled task. |
| `message` | string | Yes | The message or task description. |
| schedule params | various | Conditional | Schedule parameters (depends on action). |

Only available to the main agent.

---

### Memory

**Source:** `openbotx/tools/memory_tool.py`

#### save_memory

Persist important facts or conversation summaries.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `key` | string | Yes | A unique key for the memory entry. |
| `content` | string | Yes | The content to persist. |

Memory entries are saved to the `workspace/memory/` directory.

---

### Browser

**Source:** `openbotx/tools/browser.py`

#### browser

Chrome automation via the Chrome DevTools Protocol (CDP).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `action` | string | Yes | One of `navigate`, `click`, `type`, `screenshot`, `get_text`, `scroll`, `wait`, or `evaluate`. |

Additional parameters depend on the action. Requires Chrome to be installed on the host system.

---

### HTTP Client

**Source:** `openbotx/tools/http_client.py`

#### http_client

Make HTTP requests.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `method` | string | Yes | HTTP method: `GET`, `POST`, `PUT`, `DELETE`, `PATCH`, or `HEAD`. |
| `url` | string | Yes | The request URL. |
| `headers` | object | No | HTTP headers as key-value pairs. |
| `body` | string | No | The request body. |

---

### Image Generation

**Source:** `openbotx/tools/image.py`

#### image_generation

Generate images using AI models.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `prompt` | string | Yes | Description of the image to generate. |
| `filename` | string | Yes | Output filename for the generated image. |

Requires image generation configuration with an API key.

---

## Tool Access by Agent Type

Not all tools are available to every agent type. The main agent has full access, while subagents are restricted to a subset of tools.

| Tool | Main Agent | Subagent |
|------|------------|----------|
| `read_file` | Yes | Yes |
| `write_file` | Yes | Yes |
| `edit_file` | Yes | Yes |
| `list_dir` | Yes | Yes |
| `exec` | Yes | Yes |
| `web_search` | Yes | Yes |
| `web_fetch` | Yes | Yes |
| `http_client` | Yes | Yes |
| `browser` | Yes | No |
| `message` | Yes | No |
| `spawn` | Yes | No |
| `cron` | Yes | No |
| `save_memory` | Yes | No |
| `image_generation` | Yes | No |

Subagents have access to file operations, shell execution, web tools, and the HTTP client. Tools that interact with the user (`message`), manage other agents (`spawn`), schedule tasks (`cron`), persist state (`save_memory`), control the browser (`browser`), or generate images (`image_generation`) are restricted to the main agent.
