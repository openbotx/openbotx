# OpenBotX Architecture

OpenBotX is an AI assistant platform. It provides the infrastructure for running autonomous AI agents that communicate through multiple channels, execute tools, manage tasks, and maintain persistent memory -- all orchestrated through an async message bus.

This document describes the system architecture, core components, and data flow.

---

## Table of Contents

- [High-Level Overview](#high-level-overview)
- [Message Flow](#message-flow)
- [Real-Time Updates](#real-time-updates)
- [Core Components](#core-components)
  - [Server](#server)
  - [Message Bus](#message-bus)
  - [Agent](#agent)
  - [Channels](#channels)
  - [Providers](#providers)
  - [Tools](#tools)
  - [Tasks](#tasks)
  - [Sessions](#sessions)
  - [Cron](#cron)
  - [Config](#config)
  - [Storage](#storage)
  - [Web Client](#web-client)
- [Package Structure](#package-structure)
- [Startup Lifecycle](#startup-lifecycle)
- [Key Design Decisions](#key-design-decisions)

---

## High-Level Overview

OpenBotX is composed of the following layers:

1. **Channels** -- Ingest user messages from the web UI, Telegram, or other integrations.
2. **Message Bus** -- Async queue pair (`inbound` / `outbound`) that decouples channels from the agent.
3. **Agent Loop** -- Consumes inbound messages, runs an agentic LLM loop (call model, execute tools, repeat), and publishes the final response to the outbound queue.
4. **Channel Manager** -- Consumes outbound messages and routes them back to the originating channel.
5. **WebSocket Manager** -- Broadcasts real-time events (thinking, tool use, messages, task updates) to all connected browser clients.

Supporting services include task management, session persistence, memory consolidation, scheduled jobs (cron), and a configurable tool registry.

---

## Message Flow

The primary request/response path:

```
User
  --> Channel (Web / Telegram)
    --> MessageBus (inbound queue)
      --> AgentLoop
        --> LLM Provider (chat completion)
          --> Tool execution (if tool calls present)
            --> (repeat until no more tool calls or max iterations)
      --> MessageBus (outbound queue)
        --> ChannelManager
          --> Channel
            --> User
```

Each inbound message creates a `Task` object that tracks the request through its lifecycle: `TODO` -> `DOING` -> `DONE` (or `ERROR`).

---

## Real-Time Updates

Browser clients connect via WebSocket at `/ws` (authenticated with a JWT token in the query string). The `WebSocketManager` broadcasts events to all connected clients as the agent works:

```
AgentLoop --> WebSocketManager --> Browser
```

Event types:

| Event              | Payload                                    | Description                        |
| ------------------ | ------------------------------------------ | ---------------------------------- |
| `chat:thinking`    | `{ task_id, content }`                     | Streaming reasoning/thinking text  |
| `chat:tool_use`    | `{ task_id, tool, arguments, result }`     | Tool invocation and truncated result |
| `chat:message`     | `{ content, chat_id, task_id }`            | Final response delivered to user   |
| `task:created`     | Full task object                           | New task created                   |
| `task:updated`     | Full task object                           | Task state change                  |

The WebSocket endpoint also accepts `chat:send` messages from the browser, which are converted to `InboundMessage` objects and published to the message bus.

---

## Core Components

### Server

**Location:** `openbotx/server/`

The server is a FastAPI application with a lifespan context manager that initializes and tears down all services.

| File                | Purpose                                                                                     |
| ------------------- | ------------------------------------------------------------------------------------------- |
| `app.py`            | FastAPI app factory with lifespan. Registers all routers, middleware, WebSocket, and SPA fallback. |
| `websocket.py`      | `WebSocketManager` -- maintains a set of active connections and broadcasts JSON events. `websocket_endpoint` handles auth and bidirectional communication. |
| `auth.py`           | JWT-based `AuthMiddleware`. Protects all `/api/*` routes except `/api/auth/login`.          |
| `routes/auth.py`    | Login endpoint. Issues JWT tokens.                                                          |
| `routes/chat.py`    | Chat API (send messages, list/manage sessions).                                             |
| `routes/tasks.py`   | Task CRUD and state management.                                                             |
| `routes/files.py`   | File upload, download, and listing within the workspace.                                    |
| `routes/skills.py`  | List and load skills.                                                                       |
| `routes/channels.py`| Channel status, start/stop control.                                                         |
| `routes/providers.py`| Provider listing and configuration.                                                        |
| `routes/scheduler.py`| Cron job management API.                                                                   |
| `routes/config.py`  | Read and update platform configuration.                                                     |
| `routes/system.py`  | System info (version, health).                                                              |

The built web client (`webclient/dist/`) is served as a SPA at `/app/` with a catch-all fallback to `index.html`.

### Message Bus

**Location:** `openbotx/bus/`

The `MessageBus` is the backbone of the platform. It holds two `asyncio.Queue` instances that fully decouple message producers (channels) from the consumer (agent loop).

| File        | Purpose                                                                                   |
| ----------- | ----------------------------------------------------------------------------------------- |
| `queue.py`  | `MessageBus` with `inbound` and `outbound` async queues. Provides `publish_*` / `consume_*` methods. |
| `events.py` | Message data classes: `InboundMessage` (channel -> agent) and `OutboundMessage` (agent -> channel). |

**Session key derivation:** Each `InboundMessage` derives its session key as `{channel}:{chat_id}`, which ties all messages from the same chat to the same conversation session. This can be overridden via `session_key_override`.

### Agent

**Location:** `openbotx/agent/`

The agent subsystem is the intelligence layer of the platform.

| File           | Purpose                                                                                        |
| -------------- | ---------------------------------------------------------------------------------------------- |
| `loop.py`      | `AgentLoop` -- the main agentic loop. Consumes inbound messages, builds context, calls the LLM, executes tool calls, and repeats until a plain text response is returned or `max_iterations` (default: 40) is reached. Streams `chat:thinking` and `chat:tool_use` events via WebSocket. |
| `context.py`   | `ContextBuilder` -- assembles the system prompt from bootstrap files (`SOUL.md`, `USER.md`, `AGENTS.md`, `TOOLS.md`), persisted memory, always-on skills, and a skills summary. Provides static helpers for building OpenAI-compatible message arrays. |
| `memory.py`    | `MemoryStore` -- reads/writes `MEMORY.md` and `HISTORY.md` in the workspace `memory/` directory. Provides consolidation prompts when unconsolidated messages exceed `memory_window`. |
| `skills.py`    | `SkillsLoader` -- discovers SKILL.md files from both built-in (`openbotx/skills/`) and workspace (`workspace/skills/`) directories. Parses YAML frontmatter for metadata (name, description, always, requires). Skills marked `always: true` are injected into every system prompt. |
| `subagent.py`  | `SubagentManager` -- spawns independent background agent loops for delegated tasks. Subagents run with a restricted tool set (no `message`, `spawn`, or `cron` tools) and a lower iteration cap (15). On completion, they announce results back to the main agent via the inbound queue. |

**Agentic loop detail:**

```
1. Receive InboundMessage from bus
2. Create or resume Task (set state to DOING)
3. Load or create Session
4. Build system prompt (ContextBuilder)
5. Build message array (system + history + new user message)
6. Loop:
   a. Call LLM provider with messages + tool definitions
   b. If response contains tool_calls:
      - Execute each tool via ToolRegistry
      - Broadcast chat:tool_use via WebSocket
      - Append assistant message + tool results to messages
      - Continue loop
   c. If response is plain text:
      - Break loop, return response
7. Save messages to session
8. Publish OutboundMessage to bus
9. Set Task state to DONE
10. Check if memory consolidation is needed
```

### Channels

**Location:** `openbotx/channels/`

Channels are the communication endpoints that connect users to the platform.

| File           | Purpose                                                                                  |
| -------------- | ---------------------------------------------------------------------------------------- |
| `base.py`      | `BaseChannel` -- abstract interface defining `start()`, `stop()`, `send()`, and `is_running`. |
| `manager.py`   | `ChannelManager` -- initializes channels from config, runs an outbound dispatch loop, and routes messages. Web channel messages are forwarded through `WebSocketManager`. External channels (Telegram) go through their respective implementations. |
| `telegram.py`  | `TelegramChannel` -- Telegram bot integration via `python-telegram-bot`. Supports allowed user filtering, proxy configuration, and reply-to-message mode. |

The web channel is implicit -- it does not have a `BaseChannel` implementation. Instead, the WebSocket endpoint in the server layer handles web client communication directly, and `ChannelManager._route_message` broadcasts web-bound outbound messages via `WebSocketManager`.

### Providers

**Location:** `openbotx/providers/`

The provider subsystem abstracts LLM access behind a uniform interface.

| File                   | Purpose                                                                             |
| ---------------------- | ----------------------------------------------------------------------------------- |
| `base.py`              | `LLMProvider` abstract class and `LLMResponse` data class (content, tool_calls, reasoning_content, has_tool_calls). |
| `litellm_provider.py`  | `LiteLLMProvider` -- wraps [LiteLLM](https://github.com/BerriAI/litellm) for multi-provider LLM access. Handles model name resolution, environment variable setup, and prompt caching support. |
| `registry.py`          | `PROVIDERS` tuple of `ProviderSpec` objects. Defines metadata for each supported provider: custom, openrouter, anthropic, openai, deepseek, gemini, groq. Includes keyword matching, API key prefix detection, and gateway detection. |

**Provider resolution:** The `Config.get_provider()` method matches a model name to a provider by first checking the LiteLLM-style prefix (e.g., `anthropic/claude-sonnet-4-20250514`), then falling back to keyword matching, and finally returning any provider with an API key configured.

### Tools

**Location:** `openbotx/tools/`

Tools are the actions the agent can perform in the world.

| File               | Purpose                                                                  |
| ------------------ | ------------------------------------------------------------------------ |
| `base.py`          | Abstract `Tool` class with `name`, `description`, `parameters`, `execute()`, `validate_params()`, and `to_schema()` (OpenAI-compatible function definition). |
| `registry.py`      | `ToolRegistry` -- manages tool registration, lookup, and execution. Generates tool definition arrays for LLM calls. Appends error hints on failure to guide the agent toward recovery. |
| `filesystem.py`    | `ReadFileTool`, `WriteFileTool`, `EditFileTool`, `ListDirTool` -- workspace-scoped file operations. |
| `shell.py`         | `ExecTool` -- execute shell commands with configurable timeout and optional workspace restriction. |
| `web.py`           | `WebSearchTool` (Brave Search API), `WebFetchTool` (HTTP fetch + content extraction). |
| `message.py`       | `MessageTool` -- send messages to channels from within the agent loop. Rate-limited to one message per turn. |
| `spawn.py`         | `SpawnTool` -- delegate tasks to background subagents.                   |
| `cron.py`          | `CronTool` -- create, list, and remove scheduled jobs.                   |
| `memory_tool.py`   | `SaveMemoryTool` -- persist content to MEMORY.md and HISTORY.md.         |
| `browser.py`       | `BrowserTool` -- browser automation via CDP (Chrome DevTools Protocol).   |
| `http_client.py`   | `HttpClientTool` -- make arbitrary HTTP requests (GET, POST, PUT, DELETE, etc.). |
| `image.py`         | `ImageGenerationTool` -- generate images via configurable provider/model. |

**Subagent tool restrictions:** When `SubagentManager` builds a tool registry for a subagent, it excludes `MessageTool`, `SpawnTool`, and `CronTool` to prevent subagents from sending messages to users, spawning further subagents, or creating scheduled jobs.

### Tasks

**Location:** `openbotx/tasks/`

Tasks provide observability into what the agent is doing.

| File          | Purpose                                                                             |
| ------------- | ----------------------------------------------------------------------------------- |
| `models.py`   | `Task` dataclass with fields: `id`, `title`, `description`, `state`, `agent_type`, `parent_task_id`, `subagent_ids`, `result`, `error`, `created_at`, `updated_at`. |
| `manager.py`  | `TaskManager` -- creates tasks, tracks state transitions, and broadcasts `task:created` / `task:updated` events via WebSocket. |

Task states follow a Kanban model:

| State   | Meaning                                    |
| ------- | ------------------------------------------ |
| `TODO`  | Task created, not yet started              |
| `DOING` | Agent is actively working on the task      |
| `DONE`  | Task completed successfully                |
| `ERROR` | Task failed with an error                  |

Tasks support a parent-child relationship: subagent tasks reference their `parent_task_id`, enabling hierarchical task tracking.

### Sessions

**Location:** `openbotx/session/`

Sessions persist conversation history.

| File          | Purpose                                                                           |
| ------------- | --------------------------------------------------------------------------------- |
| `manager.py`  | `SessionManager` -- manages `Session` objects stored as JSONL files in `workspace/sessions/`. Each session is keyed by `{channel}_{chat_id}`. Provides `get_or_create`, `save`, `delete`, and `list_sessions`. Uses an in-memory cache for fast access. |

The `Session` dataclass holds a list of messages (role + content + metadata), tracks `last_consolidated` for memory consolidation, and provides `get_history()` for building LLM context (capped at 500 messages by default).

### Cron

**Location:** `openbotx/cron/`

The cron service enables scheduled task execution.

| File          | Purpose                                                                            |
| ------------- | ---------------------------------------------------------------------------------- |
| `service.py`  | `CronService` -- runs a background tick loop (every 5 seconds), checks for due jobs, and fires them by publishing an `InboundMessage` to the message bus. Persists jobs to `workspace/cron_jobs.json`. |
| `types.py`    | Data classes: `CronJob`, `CronSchedule` (kinds: `at`, `every`, `cron`), `CronPayload` (message, channel, recipient), `CronJobState` (next/last run, run count, errors), `CronStore`. |

Schedule kinds:

| Kind    | Description                                            |
| ------- | ------------------------------------------------------ |
| `at`    | One-time execution at a specific timestamp (ms)        |
| `every` | Recurring at a fixed interval (ms)                     |
| `cron`  | Standard cron expression (requires `croniter` package) |

Jobs marked `delete_after_run: true` are automatically removed after their first execution.

### Config

**Location:** `openbotx/config/`

Configuration is defined as Pydantic models and loaded from YAML.

| File          | Purpose                                                                          |
| ------------- | -------------------------------------------------------------------------------- |
| `schema.py`   | Pydantic models: `Config`, `BotConfig`, `ServerConfig`, `AgentConfig`, `ModelParams`, `ImageConfig`, `AuthConfig`, `ProviderConfig`, `ChannelsConfig`, `TelegramConfig`, `ToolsConfig`, `WebSearchConfig`, `ExecToolConfig`, `StorageConfig`, `CronConfig`. |
| `loader.py`   | `load_config()` reads YAML and expands `${ENV_VAR}` patterns. `save_config()` writes the config back to YAML. |

Key configuration sections:

| Section     | Controls                                                     |
| ----------- | ------------------------------------------------------------ |
| `bot`       | Name and description                                         |
| `server`    | Host and port                                                |
| `agents`    | Named agent configs (model, workspace, params)               |
| `auth`      | Username, password, JWT secret                               |
| `providers` | API keys and base URLs per provider                          |
| `channels`  | Telegram settings, progress/tool hint broadcasting           |
| `tools`     | Web search API key, exec timeout, workspace restriction      |
| `storage`   | Backend type (local/S3), paths, credentials                  |
| `image`     | Image generation provider, model, API key                    |
| `cron`      | Enabled flag                                                 |

### Storage

**Location:** `openbotx/storage/`

Pluggable storage backends for workspace files.

| File        | Purpose                                                |
| ----------- | ------------------------------------------------------ |
| `base.py`   | Abstract storage interface.                            |
| `local.py`  | Local filesystem storage within the workspace.         |
| `s3.py`     | AWS S3 storage backend.                                |

### Web Client

**Location:** `webclient/`

The web client is a single-page application built with:

- **Vue 3** -- component framework
- **Vite** -- build tool and dev server
- **PrimeVue 4** -- UI component library
- **Tailwind CSS 4** -- utility-first styling
- **Pinia** -- state management
- **WebSocket** -- real-time communication with the server

Pages:

| Page       | Function                                        |
| ---------- | ----------------------------------------------- |
| Chat       | Main conversation interface with real-time updates |
| TaskBoard  | Kanban board showing tasks in TODO/DOING/DONE/ERROR columns |
| Files      | File browser for the workspace                  |
| Skills     | View and manage agent skills                    |
| Channels   | Monitor and control communication channels      |
| Providers  | Configure LLM providers and API keys            |
| Scheduler  | Manage cron jobs                                |
| Settings   | Platform configuration                          |
| Login      | Authentication                                  |

---

## Package Structure

```
openbotx/
├── agent/           # AI agent loop, context building, memory, skills, subagents
│   ├── loop.py          # AgentLoop - main agentic processing loop
│   ├── context.py       # ContextBuilder - system prompt assembly
│   ├── memory.py        # MemoryStore - conversation memory persistence
│   ├── skills.py        # SkillsLoader - SKILL.md discovery and loading
│   └── subagent.py      # SubagentManager - background task delegation
├── bus/             # Async message bus
│   ├── queue.py         # MessageBus with inbound/outbound queues
│   └── events.py        # InboundMessage, OutboundMessage data classes
├── channels/        # Communication channel implementations
│   ├── base.py          # BaseChannel abstract interface
│   ├── manager.py       # ChannelManager - lifecycle and routing
│   └── telegram.py      # TelegramChannel integration
├── cli/             # CLI commands (init, start, version)
├── config/          # Configuration
│   ├── schema.py        # Pydantic configuration models
│   └── loader.py        # YAML loader with env var expansion
├── cron/            # Scheduled task service
│   ├── service.py       # CronService - tick loop and job execution
│   └── types.py         # CronJob, CronSchedule, CronPayload data classes
├── providers/       # LLM provider abstraction
│   ├── base.py          # LLMProvider and LLMResponse
│   ├── litellm_provider.py  # LiteLLM wrapper for multi-provider access
│   └── registry.py      # ProviderSpec definitions and matching
├── server/          # FastAPI server
│   ├── app.py           # Application factory and lifespan
│   ├── websocket.py     # WebSocketManager and endpoint
│   ├── auth.py          # JWT authentication middleware
│   └── routes/          # REST API endpoint routers
├── session/         # Conversation session management
│   └── manager.py       # SessionManager with JSONL persistence
├── skills/          # Built-in skill definitions (SKILL.md files)
├── storage/         # Storage backends
│   ├── base.py          # Abstract storage interface
│   ├── local.py         # Local filesystem storage
│   └── s3.py            # AWS S3 storage
├── tasks/           # Task management
│   ├── models.py        # Task model and TaskState enum
│   └── manager.py       # TaskManager with WebSocket broadcasting
├── templates/       # System prompt templates
├── tools/           # Built-in tool implementations
│   ├── base.py          # Abstract Tool class
│   ├── registry.py      # ToolRegistry - registration and execution
│   ├── filesystem.py    # read_file, write_file, edit_file, list_dir
│   ├── shell.py         # exec (shell command execution)
│   ├── web.py           # web_search, web_fetch
│   ├── message.py       # message (send to channels)
│   ├── spawn.py         # spawn (delegate to subagent)
│   ├── cron.py          # cron (manage scheduled jobs)
│   ├── memory_tool.py   # save_memory (persist to MEMORY.md/HISTORY.md)
│   ├── browser.py       # browser (CDP-based browser automation)
│   ├── http_client.py   # http_client (arbitrary HTTP requests)
│   └── image.py         # image_generation (AI image generation)
└── version.py       # Package version
```

---

## Startup Lifecycle

The FastAPI lifespan context manager in `app.py` orchestrates the full startup sequence:

```
1. Load configuration from YAML
2. Ensure workspace directory exists
3. Generate JWT secret if not configured
4. Initialize services:
   a. WebSocketManager
   b. MessageBus
   c. SessionManager
   d. TaskManager (with WebSocket reference)
   e. SkillsLoader
   f. CronService (with callback that publishes to inbound queue)
   g. LiteLLMProvider
   h. SubagentManager
   i. AgentLoop (registers all tools)
   j. ChannelManager (initializes Telegram if enabled)
5. Start background tasks:
   a. AgentLoop.run() -- consumes inbound queue
   b. CronService.run() -- tick loop for scheduled jobs
   c. ChannelManager.start() -- starts channels + outbound dispatch
6. Application is ready to serve requests
```

On shutdown, the reverse occurs: agent loop stops, cron service stops, and channels are shut down.

---

## Key Design Decisions

**Message bus decoupling.** Channels and the agent never communicate directly. The `MessageBus` with its two async queues provides a clean separation of concerns. This makes it straightforward to add new channels without modifying the agent, and allows the agent to process messages at its own pace.

**Single agent loop, multiple channels.** All messages from all channels funnel into one `AgentLoop` instance. Session isolation is achieved through the session key (`channel:chat_id`), not through separate agent instances.

**Subagents for parallelism.** When the main agent needs to delegate work, it spawns a subagent via the `SpawnTool`. Subagents run as independent `asyncio.Task` instances with their own tool registries and iteration limits. They report results back through the inbound queue, which the main agent picks up in a subsequent turn.

**Memory consolidation.** Rather than sending the entire conversation history to the LLM every time, `MemoryStore` triggers a consolidation pass when unconsolidated messages exceed the `memory_window` threshold. A separate LLM call summarizes the conversation into `MEMORY.md` (long-term facts) and `HISTORY.md` (timestamped summaries).

**Markdown-based skills.** Skills are defined as `SKILL.md` files with YAML frontmatter. This makes them easy to author, version, and share. Skills marked `always: true` are automatically included in every system prompt. Others are listed in a summary block so the agent can request them when relevant.

**Tool error recovery.** The `ToolRegistry` appends a hint (`[Analyze the error above and try a different approach.]`) to any tool execution error. This nudges the LLM toward self-correction rather than repeating the same failed action.

**YAML configuration with env var expansion.** The config loader supports `${ENV_VAR}` patterns in YAML values, allowing sensitive values (API keys) to be injected from the environment without being stored in configuration files.
