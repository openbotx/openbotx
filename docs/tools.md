# Tools Reference

OpenBotX is an AI assistant platform. Tools are Python functions the AI agent can call during conversations. This document provides a complete reference for all built-in tools, their parameters, and access rules.

## Overview

All tools are registered in `openbotx/tools/`. The `ToolRegistry` manages them and generates OpenAI-compatible function definitions for the LLM. Tools are registered during agent initialization in `AgentLoop._register_tools()`.

The registry:

1. Stores tool instances.
2. Generates OpenAI-compatible function definitions (sent to the LLM).
3. Executes tool calls by name with arguments.
4. Returns string results back to the agent loop.

### Path Resolution

All file-based tools (`read_file`, `write_file`, `edit_file`, `list_dir`, `http_client`) use the `PathResolver` class (`openbotx/helpers/path.py`) for path resolution and directory restriction enforcement.

**How it works:**

1. Relative paths are resolved against the agent's workspace directory.
2. `~` (home directory) is expanded via `Path.expanduser()`.
3. When `tools.general.restrict_to_workspace` is enabled in the config, each agent is restricted to its own **workspace directory** and the shared **public directory**. Any path outside these directories raises a `PermissionError`.
4. When `tools.general.restrict_to_workspace` is disabled, all paths on the filesystem are accessible.

```python
class PathResolver:
    def __init__(self, workspace: Path | None = None, allowed_dirs: list[Path] | None = None):
        ...

    @property
    def is_restricted(self) -> bool:
        """Returns True when directory restrictions are active."""
        return self._allowed_dirs is not None

    def resolve(self, path: str) -> Path:
        """Resolve a path string to an absolute Path, enforcing allowed directories."""
        # 1. expand ~, resolve relative to workspace
        # 2. if allowed_dirs is set, verify path is inside one of them
        # 3. raise PermissionError if outside allowed directories
        ...
```

The `ServerFactory` in `app.py` creates a `PathResolver` per agent during startup:

```python
agent_workspace = agent_cfg.resolve_workspace(self._project_path)
allowed_dirs = [agent_workspace, public_dir] if config.tools.general.restrict_to_workspace else None
resolver = PathResolver(workspace=agent_workspace, allowed_dirs=allowed_dirs)
```

This `resolver` is passed to `AgentLoop` and `SubagentManager`, which in turn pass it to all file-based tools.

### Agent-Specific Tool Whitelisting

Each agent can optionally define a `tools` list in its configuration. When set, only tools whose `name` appears in this list are registered for that agent. Tools not in the whitelist are silently skipped during `_register_tools()`. When the list is empty (default), all tools are registered.

```yaml
agents:
  crypto:
    tools: [read_file, write_file, exec, web_search, web_fetch, http_client, rss_reader, browser, message, spawn, cron, save_memory]
```

---

## Built-in Tools

### File Operations

**Source:** `openbotx/tools/filesystem.py`

All file tools receive a `PathResolver` instance at construction. When `tools.general.restrict_to_workspace` is enabled, operations are sandboxed to the agent's workspace directory and the shared public directory.

#### read_file

Read the contents of a file.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `path` | string | Yes | File path, relative to workspace or absolute. |

#### write_file

Create or overwrite a file. Creates parent directories automatically.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `path` | string | Yes | File path, relative to workspace or absolute. |
| `content` | string | Yes | The content to write. |

#### edit_file

Search and replace within a file. The `old_text` must match exactly once. If it appears multiple times, the tool returns a warning asking for more context to make it unique. If not found, it shows a best-match diff with the closest similar text.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `path` | string | Yes | File path, relative to workspace or absolute. |
| `old_text` | string | Yes | The exact text to find. |
| `new_text` | string | Yes | The replacement text. |

#### list_dir

List the contents of a directory. Items are prefixed with `[dir]` or `[file]`.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `path` | string | Yes | Directory path, relative to workspace or absolute. |

---

### Shell

**Source:** `openbotx/tools/shell.py`

#### exec

Execute a shell command.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `command` | string | Yes | The shell command to execute. |

The command runs with a configurable timeout (`tools.exec.timeout`, default 60 seconds). When `tools.general.restrict_to_workspace` is enabled (detected via `PathResolver.is_restricted`), the working directory is locked to the workspace.

---

### Web

**Source:** `openbotx/tools/web.py`

#### web_search

Search the web using the Brave Search API.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | The search query. |

Requires the Brave Search API key to be configured (`tools.web_search.api_key` in `config.yml`).

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

Additional parameters depend on the action. Requires Chrome to be installed on the host system. Each `BrowserTool` instance operates on its own tab within a shared Chrome process, enabling concurrent use by the main agent and subagents.

---

### HTTP Client

**Source:** `openbotx/tools/http_client.py`

#### http_client

Full HTTP client with download and upload support. Uses a `PathResolver` for file path resolution in download and upload operations.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `method` | string | Yes | HTTP method: `GET`, `POST`, `PUT`, `DELETE`, `PATCH`, `HEAD`, or `OPTIONS`. |
| `url` | string | Yes | The request URL. |
| `headers` | object | No | HTTP headers as key-value pairs. |
| `body` | string | No | The request body. |
| `content_type` | string | No | Body content type: `json` (default), `form`, `text`, or `xml`. Maps to the appropriate `Content-Type` header. |
| `timeout` | integer | No | Request timeout in seconds (default: 30). |
| `follow_redirects` | boolean | No | Follow HTTP redirects (default: true). |
| `download_path` | string | No | Save the response body to this file path instead of returning it. Path is resolved via `PathResolver`. |
| `upload_file` | string | No | Path to a file to upload as multipart form data. Path is resolved via `PathResolver`. |
| `upload_field` | string | No | Form field name for the uploaded file (default: `file`). |

**Content type mapping:**

| `content_type` value | `Content-Type` header |
|---------------------|----------------------|
| `json` | `application/json` |
| `form` | `application/x-www-form-urlencoded` |
| `text` | `text/plain` |
| `xml` | `application/xml` |

**Response format:** Returns JSON with `status`, `headers`, `body`, and `truncated` fields. Response bodies larger than 10,000 characters are truncated.

**Download mode:** When `download_path` is set, the file is saved and the response returns `status`, `path`, `size`, and `content_type` instead of the body.

**Upload mode:** When `upload_file` is set, the file is sent as multipart form data. The MIME type is auto-detected from the file extension. Additional form fields can be passed as JSON in the `body` parameter.

---

### RSS Reader

**Source:** `openbotx/tools/rss.py`

#### rss_reader

Read RSS and Atom feeds and return the latest entries.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `url` | string | Yes | RSS/Atom feed URL. |
| `count` | integer | No | Maximum entries to return (default: 10, max: 50). |

Supports both RSS 2.0 and Atom feed formats. Automatically detects the format by trying RSS first, then Atom. HTML tags are stripped from summary fields.

**Response format:** Returns JSON with `url`, `count`, and `entries` array. Each entry has `title`, `link`, `published`, and `summary` fields.

---

### Image Generation

**Source:** `openbotx/tools/image.py`

#### image_generation

Generate images using AI models.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `prompt` | string | Yes | Description of the image to generate. |
| `filename` | string | Yes | Output filename for the generated image. |

Requires image generation configuration with an API key. Only registered when `image.provider.api_key` is set in the config.

---

### Twitter

**Source:** `openbotx/tools/twitter.py`

#### twitter_post

Post tweets on Twitter/X. Supports text-only tweets, tweets with images from storage, and threads via reply_to_id. Uses OAuth 1.0a (HMAC-SHA1) for authentication.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `text` | string | Yes | Tweet text (max 280 characters). |
| `media_path` | string | No | Storage path to an image to attach. |
| `reply_to_id` | string | No | Tweet ID to reply to (for creating threads). |

Requires Twitter API credentials (`tools.twitter.consumer_key`) and a storage provider. Only registered when both are configured.

**Response format:** Returns JSON with `success`, `tweet_id`, and `text` on success. Returns `error` and `details` on failure.

**Media upload:** When `media_path` is provided, the image is read from storage, uploaded to the Twitter media endpoint (v1.1), and attached to the tweet (v2 API).

---

## Tool Access by Agent Type

Not all tools are available to every agent type. The main agent has full access, while subagents have a focused subset. Additionally, individual agents can restrict their tool set via the `tools` whitelist in their configuration.

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
| `rss_reader` | Yes | Yes |
| `browser` | Yes | Yes |
| `image_generation` | Yes | Yes* |
| `twitter_post` | Yes | Yes* |
| `message` | Yes | No |
| `spawn` | Yes | No |
| `cron` | Yes | No |
| `save_memory` | Yes | No |

\* `image_generation`, `twitter_post`, and `browser` are available to subagents only when their dependencies are satisfied (Chrome installed for browser, image API key configured for image_generation, Twitter API credentials configured for twitter_post).

Subagents have access to file operations, shell execution, web tools, the HTTP client, RSS reader, browser automation, image generation, and Twitter posting. Tools that interact with the user (`message`), manage other agents (`spawn`), schedule tasks (`cron`), or persist memory state (`save_memory`) are restricted to the main agent.

Both main agents and subagents share the same `PathResolver` instance, so they have identical directory access restrictions.
