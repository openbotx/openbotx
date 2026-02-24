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

---

### Chat

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat` | Send a message to the agent |
| GET | `/api/chat/sessions` | List all chat sessions |
| GET | `/api/chat/sessions/{session_id}` | Get a single session with messages |
| DELETE | `/api/chat/sessions/{session_id}` | Delete a session |

**POST /api/chat**

Sends a message asynchronously. The response is delivered via WebSocket events.

Request body:

```json
{
  "message": "string",
  "session_id": "string (optional)"
}
```

Response:

```json
{
  "task_id": "string",
  "session_id": "string"
}
```

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
| PUT | `/api/files/{path}` | Write content to a file |
| DELETE | `/api/files/{path}` | Delete a file |

**GET /api/files**

Returns a recursive tree of the workspace directory (excluding hidden files and system files).

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

**GET /api/files/download/{path}**

Returns the raw file as a `FileResponse` (binary download). Requires authentication.

**PUT /api/files/{path}**

Request body:

```json
{
  "content": "string"
}
```

**DELETE /api/files/{path}**

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
| GET | `/api/skills` | List all available skills |
| GET | `/api/skills/{name}` | Get skill content by name |

**GET /api/skills**

Response:

```json
[
  {
    "name": "string",
    "description": "string",
    "always": "boolean",
    "requires": "string[]"
  }
]
```

**GET /api/skills/{name}**

Response:

```json
{
  "name": "string",
  "content": "string"
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
    "token": "string",
    "allowed_users": ["string"],
    "...": "..."
  }
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
    "api_base": "string",
    "has_key": "boolean",
    "headers": {},
    "options": {}
  }
]
```

**PUT /api/providers/{name}**

Request body:

```json
{
  "api_key": "string",
  "api_base": "string",
  "headers": {},
  "options": {}
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
| PUT | `/api/config/{section}` | Update a configuration section |
| POST | `/api/config/restart` | Restart all services |

**PUT /api/config/{section}**

Valid sections: `bot`, `server`, `agents`, `image`, `auth`, `tools`, `storage`, `cron`, `advanced`.

Request body:

```json
{
  "data": {}
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
| `chat:message` | `{ content, chat_id, task_id }` | Final AI response |
| `chat:thinking` | `{ task_id, content }` | Agent reasoning and thinking steps |
| `chat:tool_use` | `{ task_id, tool, arguments, result }` | Tool execution details |
| `task:created` | Task object | New task was created |
| `task:updated` | Task object | Task state changed |

**chat:message**

```json
{
  "event": "chat:message",
  "data": {
    "content": "string",
    "chat_id": "string",
    "task_id": "string"
  }
}
```

**chat:thinking**

```json
{
  "event": "chat:thinking",
  "data": {
    "task_id": "string",
    "content": "string"
  }
}
```

**chat:tool_use**

```json
{
  "event": "chat:tool_use",
  "data": {
    "task_id": "string",
    "tool": "string",
    "arguments": {},
    "result": "string"
  }
}
```

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
