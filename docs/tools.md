# Tools Reference

OpenBotX is an AI assistant platform. Tools are Python functions the AI agent can call during conversations. This document provides a complete reference for all built-in tools, their parameters, and access rules.

## Overview

All tools are registered in `openbotx/tools/`. The `ToolRegistry` manages them and generates OpenAI-compatible function definitions for the LLM. Tools are registered via `build_registry()` in `openbotx/tools/registry.py`, which is called during agent initialization.

The registry:

1. Stores tool instances.
2. Generates OpenAI-compatible function definitions (sent to the LLM).
3. Executes tool calls by name with arguments.
4. Returns string results back to the agent loop.
5. Applies a global **100,000 character** truncation limit on all tool results to prevent context overflow.
6. Supports **denied_tools** filtering — `build_registry()` accepts a `denied_tools: set[str]` parameter that prevents specific tools from being registered. This is combined with the agent's `denied_tools` config field.

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

`ProjectContext.create_resolver(agent_cfg)` creates a `PathResolver` per agent. This is called inside `build_registry()` during tool registration:

```python
# In ProjectContext (openbotx/config/project.py):
def create_resolver(self, agent_cfg: AgentConfig) -> PathResolver:
    workspace = agent_cfg.resolve_workspace(self.project_path)
    allowed_dirs = (
        [workspace, self.public_dir]
        if self.tools.general.restrict_to_workspace
        else None
    )
    return PathResolver(workspace=workspace, allowed_dirs=allowed_dirs)
```

The resolver is created internally by `build_registry()` and passed to all file-based tools.

### Agent-Specific Tool Whitelisting

Each agent can optionally define a `tools` list in its configuration. When set, only tools whose `name` appears in this list are registered for that agent. Tools not in the whitelist are silently skipped during `build_registry()`. When the list is empty (default), all tools are registered.

```yaml
agents:
  crypto:
    tools: [read_file, write_file, exec, web_search, web_fetch, http_client, rss_reader, browser, message, spawn, cron, memory_save, memory_read, memory_search]
```

---

## Built-in Tools

### File Operations

**Source:** `openbotx/tools/filesystem.py`

All file tools receive a `PathResolver` instance at construction. When `tools.general.restrict_to_workspace` is enabled, operations are sandboxed to the agent's workspace directory and the shared public directory.

#### read_file

Read the contents of a file. Supports line-based pagination for large files.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `path` | string | Yes | File path, relative to workspace or absolute. |
| `offset` | integer | No | Line number to start reading from (1-based). Use to continue truncated reads. |
| `limit` | integer | No | Maximum number of lines to read. Defaults to entire file. |

**Output limit:** Each read returns up to **50 KB** of content. When a file exceeds this limit, the output includes the line range shown and the `offset` value needed to continue reading the next chunk. The agent can call `read_file` multiple times with increasing offsets to read the full file.

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

**Output limit:** Output larger than **200 KB** is truncated using tail-based truncation — only the last 200 KB of output is kept, prefixed with a warning: `[Output truncated: showing last 200000 of N chars]`. This preserves the most recent output (where errors and results typically appear) while discarding older output.

**Safety guards** — the exec tool blocks dangerous command patterns:
- Destructive file ops: `rm -rf`, `del /f`, `rmdir /s`, `shred`, `srm`, `wipe`, `truncate -s 0`, `find -delete`, `find -exec rm`
- Disk/system destruction: `format`, `mkfs`, `diskpart`, `dd if=`, writes to `/dev/` (sd, nvme, loop, mem, kmem)
- System commands: `shutdown`, `reboot`, `poweroff`, `halt`, `init 0/6`, fork bombs
- Encoding/pipe bypass: `base64 -d`, `eval`, `curl|sh`, `wget|bash`, `python|sh`
- Subshell/command substitution: `$(...)`, backtick execution
- Process substitution: `<(...)`, `>(...)`
- Environment injection: `LD_PRELOAD=`, `LD_LIBRARY_PATH=`, `DYLD_INSERT_LIBRARIES=`, `PROMPT_COMMAND=`, `PS4=`
- Dangerous redirects: writes to `/etc/`, `/proc/`, `/sys/`, `/dev/`
- ANSI-C quoting with hex, octal, or unicode escapes (`$'\x...'`, `$'\012...'`, `$'\u...'`)
- Path traversal (`../`, `..\`)
- Absolute paths outside the working directory (when workspace restriction is enabled)

---

### Web

**Source:** `openbotx/tools/web.py`

#### web_search

Search the web using the Brave Search API.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | The search query. |
| `count` | integer | No | Number of results to return (1-10). |

Requires a Brave Search API key to be configured via a credential (`tools.web_search.credential` in `config.yml`).

#### web_fetch

Fetch and extract content from a URL.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `url` | string | Yes | The URL to fetch. |
| `max_chars` | integer | No | Max characters to return (minimum: 100, default: 50000). |

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
| `label` | string | No | Optional short label for the task. |

Only available to the main agent. Creates a child task on the task board.

---

### Scheduling

**Source:** `openbotx/tools/cron.py`

#### cron

Schedule reminders and recurring tasks.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `action` | string | Yes | One of `add`, `list`, or `remove`. |
| `message` | string | Conditional | The message or task description (required for `add`). |
| `every_seconds` | integer | Conditional | Interval in seconds for recurring tasks. |
| `cron_expr` | string | Conditional | Cron expression (e.g. `0 9 * * *`). |
| `tz` | string | No | IANA timezone for cron expressions. |
| `at` | string | Conditional | ISO datetime for one-time execution. |
| `job_id` | string | Conditional | Job ID (required for `remove`). |

Only available to the main agent.

---

### Memory

**Source:** `openbotx/tools/memory_tool.py`

#### memory_save

Save conversation history and updated long-term memory. Used during memory consolidation.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `history_entry` | string | Yes | Summary of recent conversation for HISTORY.md. |
| `updated_memory` | string | Yes | Updated long-term memory content for MEMORY.md. |

#### memory_read

Read memory files on demand.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file` | string | Yes | Which file to read: `memory` for MEMORY.md, `history` for HISTORY.md. |
| `max_lines` | integer | No | Max lines to return from the end (default: all). Useful for HISTORY.md. |

#### memory_search

Search across memory and history files for specific information.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | Search term (case-insensitive substring match). |

Returns matching lines with 1 line of context before/after, prefixed with the source file and line number.

---

### Browser

**Source:** `openbotx/tools/browser.py`
**CDP Library:** `openbotx/cdp/` (vendored from [python-cdp](https://github.com/niccokunzmann/python-cdp))

#### browser

Chrome automation via the Chrome DevTools Protocol (CDP). Requires Google Chrome installed on the host system.

**Architecture:** A singleton `_ChromeInstance` manages the Chrome process (launched with `--remote-debugging-port=9222` and a persistent profile at `~/.openbotx/chrome-profile`). Each `BrowserTool` instance gets its own tab via `target.create_target`, enabling concurrent use by the main agent and subagents. The Chrome process starts lazily on the first tool call and is terminated on server shutdown.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `action` | string | Yes | One of: `navigate`, `snapshot`, `screenshot`, `click`, `type`, `press`, `inspect`, `evaluate`, `wait`. |
| `url` | string | Conditional | URL to navigate to. Required for `navigate`. |
| `selector` | string | Conditional | CSS selector. Required for `click` and `type`. |
| `text` | string | Conditional | Text to type. Required for `type`. |
| `key` | string | Conditional | Key name to press. Required for `press`. Available: Enter, Tab, Escape, Backspace, Delete, ArrowUp, ArrowDown, ArrowLeft, ArrowRight, Home, End, Space. |
| `script` | string | Conditional | JavaScript expression. Required for `evaluate`. |
| `seconds` | integer | No | Seconds to wait (default: 2). Used by `wait`. |
| `max_chars` | integer | No | Max characters for snapshot (default: 50000). |
| `headless` | boolean | No | Run browser in headless mode (default: false). |

**Actions:**

| Action | Description |
|--------|-------------|
| `navigate` | Navigate to a URL via `cdp.page.navigate`. Waits 2 seconds for page load. |
| `snapshot` | Extract visible text content (`document.body.innerText`). Truncated to `max_chars`. |
| `screenshot` | Capture a PNG screenshot via `cdp.page.capture_screenshot`. |
| `click` | Click an element by CSS selector. Uses pure CDP: resolves element to `RemoteObjectId`, scrolls into view, gets content quads for coordinates, then dispatches mouse events (mouseMoved → mousePressed → mouseReleased). |
| `type` | Click to focus an element, then type text character-by-character via CDP key events (`dispatch_key_event`). |
| `press` | Press a special key (Enter, Tab, Escape, etc.) via CDP key events with correct virtual key codes. |
| `inspect` | Discover interactive elements on the page (links, buttons, inputs, etc.). Returns up to 50 visible elements with their CSS selectors, element type, and label text. |
| `evaluate` | Run arbitrary JavaScript and return the result. |
| `wait` | Wait for a specified number of seconds. |

**Click mechanism:** The `_click` method uses a multi-step pure CDP approach:

1. **Resolve** — `runtime.evaluate` to get a `RemoteObjectId` handle for the CSS selector.
2. **Scroll** — `dom.scroll_into_view_if_needed` to ensure the element is in the viewport.
3. **Position** — `dom.get_content_quads` to get the element's bounding quad, then compute the center point.
4. **Click** — Dispatch CDP mouse events at the coordinates (mouseMoved → mousePressed → mouseReleased).

---

### HTTP Client

**Source:** `openbotx/tools/http_client.py`

#### http_client

Full HTTP client with download, upload, and authentication support. Uses a `PathResolver` for file path resolution and `CredentialConfig` for authentication via credentials.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `method` | string | Yes | HTTP method: `GET`, `POST`, `PUT`, `DELETE`, `PATCH`, `HEAD`, or `OPTIONS`. |
| `url` | string | Yes | The request URL. |
| `headers` | object | No | HTTP headers as key-value pairs. |
| `body` | string | No | The request body. |
| `content_type` | string | No | Body content type: `json` (default), `form`, `text`, or `xml`. Maps to the appropriate `Content-Type` header. |
| `auth` | string | No | Credential name from config. Automatically applies authentication headers (OAuth 1.0a, Basic, or Bearer) based on the credential's type. |
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

**Response format:** Returns JSON with `status`, `headers`, `body`, and `truncated` fields. Response bodies larger than **50,000 characters** (50 KB) are truncated.

**Download mode:** When `download_path` is set, the file is saved and the response returns `status`, `path`, `size`, and `content_type` instead of the body.

**Upload mode:** When `upload_file` is set, the file is sent as multipart form data. The MIME type is auto-detected from the file extension. Additional form fields can be passed as JSON in the `body` parameter.

**Authentication:** When `auth` is set, the tool looks up the named credential from `credentials` in the config and applies the appropriate `Authorization` header. The http_client automatically has access to all credentials with compatible types (oauth1, basic, simple):

| Auth type | Credential fields | Header format |
|-----------|---------------------|---------------|
| `oauth1` | `consumer_key`, `consumer_secret`, `access_token`, `access_token_secret` | `OAuth oauth_consumer_key="...", ...` (HMAC-SHA1) |
| `basic` | `username`, `password` | `Basic base64(username:password)` |
| `simple` | `key` | `Bearer {key}` |

Config example:
```yaml
credentials:
  twitter:
    type: oauth1
    consumer_key: ${TWITTER_CONSUMER_KEY}
    consumer_secret: ${TWITTER_CONSUMER_SECRET}
    access_token: ${TWITTER_ACCESS_TOKEN}
    access_token_secret: ${TWITTER_ACCESS_TOKEN_SECRET}
  my_api:
    type: simple
    key: ${MY_API_TOKEN}
```

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

#### generate_image

Generate images using AI models.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `prompt` | string | Yes | Description of the image to generate or edit. |
| `filename` | string | Yes | Output filename for the generated image. |
| `reference_images` | array | No | List of storage paths to reference images for image-to-image editing. |

Requires image generation configuration. The `image.model` field uses the same `provider/model` format as agents (e.g. `openai/dall-e-3`). Only registered when the model's provider prefix matches a configured provider with a valid credential.

---

## Tool Access by Agent Type

Not all tools are available to every agent type. The main agent has full access, while subagents have a focused subset. Additionally, individual agents can restrict their tool set via the `tools` whitelist in their configuration.

| Tool | Main Agent | Subagent |
|------|------------|----------|
| `read_file` | Yes | Yes |
| `write_file` | Yes | Yes |
| `edit_file` | Yes | Yes |
| `list_dir` | Yes | Yes |
| `exec` | Yes | No |
| `web_search` | Yes | Yes |
| `web_fetch` | Yes | Yes |
| `http_client` | Yes | Yes |
| `rss_reader` | Yes | Yes |
| `browser` | Yes | No |
| `generate_image` | Yes | Yes* |
| `message` | Yes | No |
| `spawn` | Yes | No |
| `cron` | Yes | No |
| `memory_save` | Yes | No |
| `memory_read` | Yes | No |
| `memory_search` | Yes | No |

\* `generate_image` is available to subagents only when its dependencies are satisfied (image API key configured).

Subagents have access to file operations, web tools, the HTTP client, RSS reader, and image generation. Tools that interact with the user (`message`), manage other agents (`spawn`), schedule tasks (`cron`), access memory (`memory_save`, `memory_read`, `memory_search`), execute shell commands (`exec`), or automate the browser (`browser`) are restricted to the main agent.

Both main agents and subagents share the same `PathResolver` instance, so they have identical directory access restrictions.
