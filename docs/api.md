# OpenBotX API Reference

Complete REST API and WebSocket reference for OpenBotX.

---

## Authentication

All endpoints (except `/api/auth/login`) require a valid JWT token passed in the `Authorization` header:

```
Authorization: Bearer <token>
```

---

## REST API

All endpoints are prefixed with `/api/`.

---

### Auth

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login` | Authenticate and obtain a JWT token |

**POST /api/auth/login**

No authentication required.

Request body:

```json
{
  "username": "string",
  "password": "string"
}
```

Response:

```json
{
  "token": "string"
}
```

---

### System

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/version` | Server version |
| GET | `/api/system/info` | System information (OS, CPU, memory, disk, GPU) |

**GET /api/health**

Response:

```json
{
  "status": "ok",
  "version": "string"
}
```

**GET /api/version**

Response:

```json
{
  "version": "string"
}
```

**GET /api/system/info**

Response:

```json
{
  "os": { "system": "string", "release": "string", "version": "string", "machine": "string" },
  "cpu": { "processor": "string", "cores": 0 },
  "memory": { "total_gb": 0.0 },
  "disk": { "total_gb": 0.0, "used_gb": 0.0, "free_gb": 0.0, "percent": 0.0 },
  "gpu": [{ "name": "string" }],
  "python": "string",
  "version": "string"
}
```

---

### Chat

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat` | Send a message to the agent |
| POST | `/api/chat/upload` | Upload media files (images, audio) |
| GET | `/api/chat/sessions` | List all chat sessions |
| GET | `/api/chat/sessions/{session_id}` | Get a single session with messages |
| DELETE | `/api/chat/sessions/{session_id}` | Delete a session |

**POST /api/chat**

Sends a message asynchronously. The response is delivered via WebSocket events.

Request body:

```json
{
  "message": "string",
  "session_id": "string (optional)",
  "media": ["string (optional)"]
}
```

The `media` field accepts an array of storage paths (e.g., from `/api/chat/upload`). Images are sent to the LLM as data URIs. Audio files are transcribed via faster-whisper and the transcript is prepended to the message content.

The message is persisted to the session immediately (before the async agent loop processes it). This means a page refresh always shows the session and the user's message, even if the agent hasn't responded yet.

Response:

```json
{
  "task_id": "string",
  "session_id": "string"
}
```

**POST /api/chat/upload**

Upload media files (images, audio). Accepts multipart form data. Files are stored in date-organized subdirectories under `public/media/` (e.g., `public/media/2026/02/26/`) with a generated filename.

Request: `multipart/form-data` with one or more file fields.

Response:

```json
{
  "paths": ["public/media/2026/02/26/abc123def456.jpg"]
}
```

The returned paths can be passed in the `media` field of `POST /api/chat`.

**GET /api/chat/sessions**

Response:

```json
[
  {
    "key": "string",
    "created_at": "string",
    "updated_at": "string"
  }
]
```

**GET /api/chat/sessions/{session_id}**

The `session_id` is resolved using key resolution:
- If it contains `:`, used as the session key directly (e.g., `web:abc123`, `heartbeat:heartbeat`)
- Otherwise, prefixed with `web:` (standard user sessions)

Response:

```json
{
  "key": "string",
  "messages": [],
  "created_at": "string",
  "updated_at": "string"
}
```

**DELETE /api/chat/sessions/{session_id}**

Uses the same key resolution as GET.

Response:

```json
{
  "status": "deleted"
}
```

---

### Tasks

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/tasks` | List active tasks (done/error tasks older than 24h are excluded) |
| GET | `/api/tasks/{task_id}` | Get a single task |
| PATCH | `/api/tasks/{task_id}` | Update task state |

**GET /api/tasks**

Returns all `TODO` and `DOING` tasks, plus `DONE` and `ERROR` tasks from the last 24 hours.

Each task object includes:

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Task identifier |
| `title` | string | Short title |
| `state` | string | `TODO`, `DOING`, `DONE`, or `ERROR` |
| `agent_name` | string | Name of the agent handling this task |
| `tool_count` | int | Number of tool calls executed |
| `iteration_count` | int | Number of LLM call iterations |
| `token_usage` | object | Cumulative token usage: `{ prompt_tokens, completion_tokens, total_tokens }`. Empty object if no LLM calls were made |
| `duration_ms` | int\|null | Milliseconds from start to completion |

**PATCH /api/tasks/{task_id}**

Request body:

```json
{
  "state": "TODO | DOING | DONE | ERROR"
}
```

---

### Files

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/files` | Get workspace file tree |
| GET | `/api/files/{path}` | Read file metadata or content |
| GET | `/api/files/download/{path}` | Download raw file |
| POST | `/api/files/create/{path}` | Create an empty file |
| POST | `/api/files/mkdir/{path}` | Create a directory |
| POST | `/api/files/upload/{path}` | Upload files to a directory |
| POST | `/api/files/upload` | Upload files to the root directory |
| PUT | `/api/files/{path}` | Write content to a file |
| DELETE | `/api/files/{path}` | Delete a file or directory (recursive) |

**GET /api/files**

Returns a recursive tree of the workspace directory (excluding hidden files, system files, and protected files like `config.yml`).

**GET /api/files/{path}**

Returns file info. The response format depends on the file type:

For text files (`.md`, `.txt`, `.json`, `.yaml`, `.py`, `.js`, `.html`, etc.):

```json
{
  "path": "string",
  "type": "text",
  "content": "string"
}
```

For media and binary files (`image`, `video`, `audio`, `binary`):

```json
{
  "path": "string",
  "type": "image | video | audio | binary",
  "mime": "string",
  "size": 0,
  "url": "string"
}
```

The `url` field points to `/public/{path}` for files under the `public/` directory (no auth required, suitable for `<img>`, `<video>`, `<audio>` tags), or `/api/files/download/{path}` for other files.

**POST /api/files/create/{path}**

Creates an empty file at the specified path. Parent directories are created automatically.

Response:

```json
{
  "status": "created"
}
```

**POST /api/files/mkdir/{path}**

Creates a directory at the specified path. Parent directories are created automatically.

Response:

```json
{
  "status": "created"
}
```

**POST /api/files/upload/{path}**

Upload files to the specified directory. Accepts multipart form data. `POST /api/files/upload` uploads to the root directory.

Request: `multipart/form-data` with one or more file fields.

Response:

```json
{
  "status": "ok",
  "paths": ["path/to/uploaded_file.txt"]
}
```

**GET /api/files/download/{path}**

Returns the raw file as a binary download. Requires authentication.

**PUT /api/files/{path}**

Request body:

```json
{
  "content": "string"
}
```

**DELETE /api/files/{path}**

Deletes a file or directory. Directories are deleted recursively.

Response:

```json
{
  "status": "deleted"
}
```

---

### Public Files

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/public/{path}` | Serve files from the `public/` directory |

No authentication required. Files under the project's `public/` directory are served directly. This allows media files (images, video, audio) to be rendered in HTML5 tags without needing auth headers.

---

### Skills

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/skills` | List all skills |
| GET | `/api/skills/{name}` | Get a skill's raw content |
| PUT | `/api/skills/{name}` | Update a skill's SKILL.md |
| DELETE | `/api/skills/{name}` | Delete a skill directory |

All endpoints support an optional `?agent=` query parameter to target a specific location. For nested skills, the name includes the publisher prefix (e.g., `/api/skills/anthropic/pdf`).

**GET /api/skills**

Supports an optional `agent` query parameter:

- No parameter: returns all skills across all locations (project and each workspace shown independently)
- `agent=` (empty): returns built-in + project skills only
- `agent=<name>`: returns built-in + project + that agent's workspace skills

Response:

```json
[
  {
    "name": "string",
    "description": "string",
    "always": "boolean",
    "source": "builtin | project | workspace",
    "publisher": "string",
    "agent": "string"
  }
]
```

**GET /api/skills/{name}**

Response:

```json
{
  "name": "string",
  "content": "string",
  "source": "builtin | project | workspace"
}
```

**PUT /api/skills/{name}**

Request body:

```json
{
  "content": "string"
}
```

Built-in skills cannot be edited.

**DELETE /api/skills/{name}**

Built-in skills cannot be deleted. Empty parent directories are cleaned up automatically.

---

### Marketplace

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/marketplace/targets` | List install targets (project + agents) |
| GET | `/api/marketplace/check/{source}/{name}` | Check if a skill is already installed |
| POST | `/api/marketplace/install` | Install a skill from the marketplace |

**GET /api/marketplace/targets**

Returns available install locations.

Response:

```json
[
  { "label": "Project", "value": "" },
  { "label": "Agent: main", "value": "main" }
]
```

**GET /api/marketplace/check/{source}/{name}**

Supports `?agent=` to check a specific location.

Response:

```json
{
  "installed": "boolean"
}
```

**POST /api/marketplace/install**

Downloads and installs a skill package from the marketplace catalog.

Request body:

```json
{
  "source": "string",
  "name": "string",
  "agent": "string (optional, default: project)"
}
```

If the skill already exists at the target location, it is replaced.

Response:

```json
{
  "ok": true
}
```

---

### Channels

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/channels` | Get status of all channels |
| GET | `/api/channels/{name}` | Get channel details |
| PUT | `/api/channels/{name}` | Update channel configuration |
| POST | `/api/channels/{name}/start` | Start a channel |
| POST | `/api/channels/{name}/stop` | Stop a channel |

**GET /api/channels**

Response:

```json
{
  "web": {
    "running": "boolean"
  },
  "telegram": {
    "running": "boolean",
    "type": "string",
    "enabled": "boolean"
  }
}
```

**PUT /api/channels/{name}**

Request body:

```json
{
  "config": {
    "credential": "string",
    "allowed_users": ["string"],
    "...": "..."
  }
}
```

**POST /api/channels/{name}/start**

Starts the channel. For Telegram, also persists `enabled: true` to `config.yml` so the channel auto-starts on the next server boot.

Response:

```json
{
  "status": "started"
}
```

**POST /api/channels/{name}/stop**

Stops the channel. For Telegram, also persists `enabled: false` to `config.yml` so the channel stays stopped on the next server boot.

Response:

```json
{
  "status": "stopped"
}
```

---

### Credentials

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/credentials` | List all credentials (sensitive values masked) |
| POST | `/api/credentials` | Create a new credential |
| PUT | `/api/credentials/{name}` | Update a credential |
| DELETE | `/api/credentials/{name}` | Delete a credential |

**GET /api/credentials**

Response:

```json
[
  {
    "name": "string",
    "type": "string",
    "...": "type-specific fields (sensitive values masked)"
  }
]
```

**POST /api/credentials**

Request body:

```json
{
  "name": "string",
  "type": "string",
  "...": "type-specific fields"
}
```

**PUT /api/credentials/{name}**

Request body:

```json
{
  "type": "string",
  "...": "type-specific fields"
}
```

**DELETE /api/credentials/{name}**

Response:

```json
{
  "status": "deleted"
}
```

---

### Providers

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/providers` | List all LLM providers |
| PUT | `/api/providers/{name}` | Update provider configuration |

**GET /api/providers**

Response:

```json
[
  {
    "name": "string",
    "configured": "boolean",
    "credential": "string",
    "has_key": "boolean",
    "base_url": "string",
    "request_headers": {},
    "request_options": {},
    "model_params": {}
  }
]
```

**PUT /api/providers/{name}**

Request body:

```json
{
  "credential": "string",
  "base_url": "string",
  "request_headers": {},
  "request_options": {},
  "model_params": {}
}
```

---

### Agents

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/agents` | List all configured agents |

**GET /api/agents**

Response:

```json
[
  {
    "name": "string",
    "description": "string",
    "model": "string"
  }
]
```

---

### Tools

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/tools` | List all registered tools |

**GET /api/tools**

Response:

```json
[
  {
    "name": "string",
    "description": "string",
    "parameters": {}
  }
]
```

---

### Forms

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/forms` | Get dynamic form schemas for the frontend |

**GET /api/forms**

Returns form schema definitions used by the frontend's `DynamicForm` component to render configuration forms dynamically.

Each field in the schema has `name`, `type`, `label`, and optional `required`, `placeholder`, `options` (for select), and `visible_when` (conditional visibility).

Supported field types:

| Type | Component | Description |
|------|-----------|-------------|
| `text` | InputText | Standard text input |
| `email` | InputText | Email input |
| `int` | InputNumber | Integer input |
| `float` | InputNumber | Decimal input |
| `bool` | ToggleSwitch | Boolean toggle |
| `secret` | Password | Masked input with toggle |
| `long-text` | Textarea | Multi-line text |
| `select` | Select | Dropdown with static options |
| `credential` | Select | Dropdown of available credentials |
| `provider` | Select | Dropdown of available providers |
| `datetime` | DatePicker | Date and time picker |
| `date` | DatePicker | Date only picker |
| `time` | DatePicker | Time only picker (24h) |
| `color` | ColorPicker | Color selector |

Response:

```json
{
  "form_name": [
    { "name": "field_name", "type": "text", "label": "Field Label", "required": true }
  ]
}
```

---

### Scheduler

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/scheduler/jobs` | List all scheduled jobs |
| POST | `/api/scheduler/jobs` | Create a new scheduled job |
| DELETE | `/api/scheduler/jobs/{job_id}` | Delete a scheduled job |

**POST /api/scheduler/jobs**

Request body:

```json
{
  "name": "string",
  "message": "string",
  "cron_expr": "string (optional)",
  "every_seconds": "number (optional)",
  "at": "string (optional)",
  "timezone": "string (optional)",
  "channel": "string (optional)",
  "to": "string (optional)"
}
```

Provide exactly one scheduling strategy: `cron_expr`, `every_seconds`, or `at`.

---

### Config

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/config` | Get full configuration (sensitive values masked) |
| GET | `/api/config/yaml` | Get full configuration as YAML string (sensitive values masked) |
| POST | `/api/config/validate` | Validate a YAML configuration string |
| PATCH | `/api/config` | Update multiple configuration sections in a single call |
| PUT | `/api/config/{section}` | Update a single configuration section |
| POST | `/api/config/restart` | Restart all services |

**GET /api/config/yaml**

Returns the full configuration as a YAML string with sensitive values masked.

Response:

```json
{
  "yaml": "string"
}
```

**POST /api/config/validate**

Validates a YAML configuration string against the Config schema.

Request body:

```json
{
  "yaml": "string"
}
```

Response (valid):

```json
{
  "valid": true
}
```

Response (invalid):

```json
{
  "valid": false,
  "error": "string",
  "line": "number (optional)"
}
```

**PATCH /api/config**

Update multiple sections in a single call (one disk write).

Request body:

```json
{
  "sections": {
    "bot": { "name": "MyBot" },
    "server": { "port": 9000 }
  }
}
```

**PUT /api/config/{section}**

Valid sections: `bot`, `server`, `agents`, `image`, `web_client`, `tools`, `storage`, `cron`, `credentials`, `providers`, `advanced`.

Request body:

```json
{
  "data": {}
}
```

For the `advanced` section, the `data` field can contain a `yaml` key with the full YAML configuration string:

```json
{
  "data": {
    "yaml": "bot:\n  name: MyBot\n..."
  }
}
```

**POST /api/config/restart**

Restarts the agent loop, channels, and cron scheduler. No request body required.

---

## WebSocket

### Connection

Connect to the WebSocket endpoint with a valid JWT token as a query parameter:

```
ws://host:port/ws?token=JWT_TOKEN
```

### Events

#### Server to Client

| Event | Payload | Description |
|-------|---------|-------------|
| `chat:stream` | `{ task_id, chat_id, content, agent_name }` | Real-time token streaming — sent for each chunk of text as the LLM generates it |
| `chat:stream_end` | `{ task_id, chat_id, agent_name }` | End of streaming response (only for content-only responses, not when tool calls follow) |
| `chat:message` | `{ content, chat_id, task_id, agent_name }` | Final AI response — `content` is a block array |
| `chat:thinking` | `{ task_id, chat_id, content, agent_name }` | Agent reasoning and thinking steps |
| `chat:tool_use` | `{ task_id, chat_id, tool, description, agent_name }` | Tool execution details |
| `chat:user_message` | `{ chat_id, content, media, channel }` | Non-web user message received (e.g., from Telegram, cron) |
| `chat:transcription` | `{ chat_id, content }` | Audio media transcription result |
| `task:created` | Task object | New task was created |
| `task:updated` | Task object | Task state changed |
| `channel:status` | `{ name, running }` | Channel connection status changed |
| `sessions:updated` | `{}` | Session list changed (reload sidebar) |

**chat:stream**

```json
{
  "event": "chat:stream",
  "data": {
    "task_id": "string",
    "chat_id": "string",
    "content": "string (token chunk)",
    "agent_name": "string"
  }
}
```

The frontend should accumulate `content` chunks and render them progressively. When `chat:stream_end` is received, finalize the message display.

**chat:stream_end**

```json
{
  "event": "chat:stream_end",
  "data": {
    "task_id": "string",
    "chat_id": "string",
    "agent_name": "string"
  }
}
```

**chat:message**

```json
{
  "event": "chat:message",
  "data": {
    "content": [
      { "type": "text", "text": "string" },
      { "type": "tool_use", "name": "string", "description": "string" }
    ],
    "chat_id": "string",
    "task_id": "string",
    "agent_name": "string"
  }
}
```

The `content` array is the authoritative source of the complete response. It contains the same structured blocks persisted to the session JSONL. The frontend uses this directly instead of client-accumulated streaming chunks, guaranteeing completeness even if stream tokens were lost.

**chat:thinking**

```json
{
  "event": "chat:thinking",
  "data": {
    "task_id": "string",
    "chat_id": "string",
    "content": "string",
    "agent_name": "string"
  }
}
```

**chat:tool_use**

```json
{
  "event": "chat:tool_use",
  "data": {
    "task_id": "string",
    "chat_id": "string",
    "tool": "string",
    "description": "string",
    "agent_name": "string"
  }
}
```

All `chat:*` events include `chat_id` and `agent_name` so the frontend can filter messages by session and identify which agent is responding. Only messages matching the active session should be displayed — others are silently ignored until the user switches to that session.

#### Client to Server

| Event | Payload | Description |
|-------|---------|-------------|
| `chat:send` | `{ data: { message, session_id, metadata? } }` | Send a chat message |

**chat:send**

Alternative to `POST /api/chat`. Sends a message through the WebSocket connection.

```json
{
  "event": "chat:send",
  "data": {
    "message": "string",
    "session_id": "string (optional)",
    "metadata": {}
  }
}
```
