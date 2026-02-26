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
  - [Heartbeat](#heartbeat)
  - [Config](#config)
  - [Helpers](#helpers)
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
3. **Orchestrator** -- Consumes inbound messages, classifies them to the appropriate agent (when multiple agents are configured), and delegates processing.
4. **Agent Loop** -- Runs an agentic LLM loop (call model, execute tools, repeat), and publishes the final response to the outbound queue.
5. **Channel Manager** -- Consumes outbound messages and routes them back to the originating channel.
6. **Event Dispatcher** -- Broadcasts real-time events (thinking, tool use, messages, task updates) through registered handlers (e.g. `WebSocketManager`). Decouples event producers from the transport layer.

Supporting services include task management, session persistence, memory consolidation, scheduled jobs (cron), and a configurable tool registry.

---

## Message Flow

The primary request/response path:

```
User
  --> Channel (Web / Telegram)
    --> MessageBus (inbound queue)
      --> Orchestrator
        --> AgentClassifier (selects agent, if multi-agent)
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

| Event                | Payload                                                  | Description                                        |
| -------------------- | -------------------------------------------------------- | -------------------------------------------------- |
| `chat:thinking`      | `{ task_id, chat_id, content, agent_name }`              | Streaming reasoning/thinking text                  |
| `chat:tool_use`      | `{ task_id, chat_id, tool, description, agent_name }`    | Tool invocation with human-readable description    |
| `chat:message`       | `{ content, chat_id, task_id, agent_name }`              | Final response delivered to user                   |
| `chat:user_message`  | `{ chat_id, content, media, channel }`                   | Non-web user message received (for real-time display in the web UI) |
| `chat:transcription` | `{ chat_id, content }`                                   | Audio transcription result (when media contains audio) |
| `task:created`       | Full task object                                         | New task created                                   |
| `task:updated`       | Full task object                                         | Task state change                                  |
| `sessions:updated`   | `{}`                                                     | Session list changed (reload sidebar)              |
| `channel:status`     | `{ name, running }`                                      | Channel connection status changed                  |

The WebSocket endpoint also accepts `chat:send` messages from the browser, which are converted to `InboundMessage` objects and published to the message bus.

---

## Core Components

### Server

**Location:** `openbotx/server/`

The server is a FastAPI application with a lifespan context manager that initializes and tears down all services. The `ServerFactory` class encapsulates all dependency creation logic.

| File                | Purpose                                                                                     |
| ------------------- | ------------------------------------------------------------------------------------------- |
| `app.py`            | `ServerFactory` -- builds all server dependencies from config (providers, storage, orchestrator, cron callbacks). `lifespan()` -- async context manager that initializes and tears down all services. `create_app()` -- FastAPI app factory that registers all routers, middleware, WebSocket, and SPA fallback. |
| `websocket.py`      | `WebSocketManager` -- maintains a set of active connections and broadcasts JSON events. `websocket_endpoint` handles auth and bidirectional communication. |
| `auth.py`           | JWT-based `AuthMiddleware`. Protects all `/api/*` routes except `/api/auth/login`.          |
| `routes/auth.py`    | Login endpoint. Issues JWT tokens.                                                          |
| `routes/chat.py`    | Chat API (send messages, list/manage sessions).                                             |
| `routes/tasks.py`   | Task CRUD and state management.                                                             |
| `routes/files.py`   | File API: tree listing, read (returns JSON with type-based content or metadata), download (raw binary), create file, create directory, write, and delete (files and directories). Uses `StorageProvider` abstraction for all operations. Classifies files as `text`, `image`, `video`, `audio`, or `binary`. |
| `routes/skills.py`  | List, load, and update skills. GET lists all skills, GET by name returns raw content with source, PUT updates project skills (validates source is not builtin). |
| `routes/tools.py`   | List registered tools with their definitions (name, description, parameters).               |
| `routes/channels.py`| Channel status, configuration, start/stop control. Persists `enabled` state on start/stop for auto-start on boot. |
| `routes/providers.py`| Provider listing and configuration.                                                        |
| `routes/scheduler.py`| Cron job management API.                                                                   |
| `routes/config.py`  | Read and update platform configuration. Includes YAML export, YAML validation, and service restart. |
| `routes/system.py`  | System info (version, health).                                                              |
| `routes/agents.py`  | Agent listing and configuration.                                                            |

**ServerFactory** encapsulates all dependency creation:

| Method                  | Purpose                                                                              |
| ----------------------- | ------------------------------------------------------------------------------------ |
| `create_provider(model)` | Resolves the model to a provider config and creates a `LiteLLMProvider`.            |
| `create_storage(url)`   | Creates `S3Storage` or `LocalStorage` based on the config.                           |
| `create_cron_callback(bus)` | Returns a callback that publishes `InboundMessage` to the bus when a cron job fires. |
| `create_orchestrator(...)` | Builds all `AgentLoop` instances (one per agent), creates `SubagentManager`s, `PathResolver`s, and the `AgentClassifier`. Returns an `Orchestrator` that routes messages. |
| `setup_logging(path)`   | Configures rotating file handler + console handler for the `openbotx` logger.        |

The built web client (`openbotx/webclient/`) is served as a SPA at `/app/` with a catch-all fallback to `index.html` (served with `Cache-Control: no-cache` to prevent stale bundles). The build output lives inside the Python package so it is included in the `.whl` distribution — users who install via `pip install openbotx` get the web UI out of the box.

Files under the project's `public/` directory are served at `/public/{path}` without authentication. This allows media files (images, video, audio) to be embedded in HTML5 tags (`<img>`, `<video>`, `<audio>`) without needing auth headers.

### Message Bus

**Location:** `openbotx/bus/`

The `MessageBus` is the backbone of the platform. It holds two `asyncio.Queue` instances that fully decouple message producers (channels) from the consumer (orchestrator/agent loop).

| File            | Purpose                                                                                   |
| --------------- | ----------------------------------------------------------------------------------------- |
| `queue.py`      | `MessageBus` with `inbound` and `outbound` async queues. Provides `publish_*` / `consume_*` methods. |
| `events.py`     | Message data classes: `InboundMessage` (channel -> agent) and `OutboundMessage` (agent -> channel). |
| `dispatcher.py` | `EventDispatcher` -- protocol-based event broadcasting. Components call `dispatcher.broadcast(event, data)` instead of coupling directly to WebSocketManager. Handlers (like WebSocketManager) register via `add_handler()`. |

**Session key derivation:** Each `InboundMessage` derives its session key as `{channel}:{chat_id}`, which ties all messages from the same chat to the same conversation session. This can be overridden via `session_key_override`.

### Agent

**Location:** `openbotx/agent/`

The agent subsystem is the intelligence layer of the platform.

| File              | Purpose                                                                                        |
| ----------------- | ---------------------------------------------------------------------------------------------- |
| `orchestrator.py` | `Orchestrator` -- consumes inbound messages from the bus, routes them to the appropriate agent via `AgentClassifier` (or directly to the default agent when only one exists), and delegates processing to the selected `AgentLoop`. |
| `classifier.py`   | `AgentClassifier` -- LLM-based message classifier. Analyzes the user's message and recent conversation history to select the best agent using a `route` tool call. Falls back to the first agent on error. Only instantiated when multiple agents are configured. |
| `loop.py`         | `AgentLoop` -- the main agentic loop. Consumes inbound messages, builds context, calls the LLM, executes tool calls, and repeats until a plain text response is returned or `max_iterations` (default: 40) is reached. Streams `chat:thinking`, `chat:tool_use`, `chat:user_message`, and `chat:transcription` events via the EventDispatcher. Broadcasts `sessions:updated` after saving each conversation turn. Each agent has its own `AgentLoop` instance with its own `PathResolver`, workspace, model, and tool registry. |
| `context.py`      | `ContextBuilder` -- assembles the system prompt from bootstrap files (`SOUL.md`, `USER.md`, `AGENTS.md`, `TOOLS.md`), persisted memory, always-on skills, a skills summary, the public URL (when configured), and agent-specific instructions. Provides the directory context (workspace and public paths) and static helpers for building OpenAI-compatible message arrays with multimodal support (text + images). `add_tool_result()` appends tool results to messages without truncation — each tool manages its own output limits internally. |
| `memory.py`       | `MemoryStore` -- reads/writes `MEMORY.md` and `HISTORY.md` in the workspace `memory/` directory. Auto-creates the `memory/` directory on initialization. Provides consolidation prompts when unconsolidated messages exceed `memory_window`. Consolidation input includes only user/assistant text messages (tool calls and tool results are excluded). |
| `skills.py`       | `SkillsLoader` -- discovers SKILL.md files from both built-in (`openbotx/skills/`) and workspace (`workspace/skills/`) directories. Parses YAML frontmatter for metadata (name, description, always, requires). Each skill is tagged with a `source` field (`"builtin"` or `"project"`) and a `location` field (absolute path to the SKILL.md file, included in the skills summary XML so the LLM can read the file if needed). Skills marked `always: true` are injected into every system prompt, but only if their requirements are satisfied. Provides `load_skill_raw()` for the REST API (returns raw content with frontmatter + source) and `save_skill()` for updating project skills (validates source is not builtin). |
| `subagent.py`     | `SubagentManager` -- spawns independent background agent loops for delegated tasks. Subagents run with a focused tool set (no `message`, `spawn`, `cron`, or `save_memory` tools), a lower iteration cap (15), and hardcoded `max_tokens=4096`, `temperature=0.1`. Their system prompt includes workspace and public directory absolute paths. They share the same `PathResolver` as the parent agent. Tool results are truncated to 500 characters inline (not via ContextBuilder). On completion, they announce results back to the main agent via the inbound queue with `system_message: true` metadata. |

**Multi-agent orchestration:**

When multiple agents are defined in the config, the `Orchestrator` uses the `AgentClassifier` to determine which agent should handle each message:

```
1. Orchestrator receives InboundMessage from bus (1-second timeout polling for graceful shutdown)
2. If single agent → route to default agent (no classification overhead)
3. If multiple agents → call AgentClassifier:
   a. Build system prompt listing all agents and their descriptions
   b. Prepare history: last 20 messages, assistant messages prefixed with [Agent: name]
   c. Send to LLM (max_tokens=256, temperature=0.0)
   d. LLM calls `route(agent_name, confidence)` tool
   e. Validate agent_name exists in configured agents
   f. Return agent_name (or default on unknown/error)
4. Delegate message processing to selected AgentLoop
```

The classifier uses the model specified in `classifier.model` (config), falling back to the default agent's model if not set.

**Classifier system prompt rules:**

The classifier operates with four rules:

1. Analyze the user's latest message and the conversation history.
2. **Continuity bias:** If the conversation was previously handled by a specific agent, continue with that agent unless the topic clearly changes. This prevents unnecessary agent switches mid-conversation.
3. Use the `route` tool to select the best agent.
4. Always select exactly one agent from the available list.

Assistant messages in the classifier's history include an `[Agent: name]` prefix (e.g., `[Agent: crypto] Here's the market data...`), so the classifier can see which agent handled previous turns and maintain continuity.

**Orchestrator error resilience:**

The orchestrator's `run()` loop catches exceptions per-message. If a single message fails (e.g., the agent loop throws), the error is logged but the orchestrator continues processing the next message. This prevents one bad request from crashing the entire system. The 1-second timeout on `consume_inbound()` allows the stop event to be checked regularly for graceful shutdown.

**Agentic loop detail:**

```
1. Receive InboundMessage from Orchestrator
2. Create or resume Task (set state to DOING)
3. Load or create Session
4. Build system prompt (ContextBuilder)
5. Build message array (system + history + new user message)
6. Loop:
   a. Call LLM provider with messages + tool definitions
   b. If response contains tool_calls:
      - Execute each tool via ToolRegistry
      - Broadcast chat:tool_use via EventDispatcher
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
| `filesystem.py`    | `ReadFileTool`, `WriteFileTool`, `EditFileTool`, `ListDirTool` -- file operations using `PathResolver` for path resolution and directory restriction enforcement. |
| `shell.py`         | `ExecTool` -- execute shell commands with configurable timeout and optional workspace restriction. |
| `web.py`           | `WebSearchTool` (Brave Search API), `WebFetchTool` (HTTP fetch + content extraction). |
| `message.py`       | `MessageTool` -- send messages to channels from within the agent loop. Rate-limited to one message per turn. |
| `spawn.py`         | `SpawnTool` -- delegate tasks to background subagents.                   |
| `cron.py`          | `CronTool` -- create, list, and remove scheduled jobs.                   |
| `memory_tool.py`   | `SaveMemoryTool` -- persist content to MEMORY.md and HISTORY.md.         |
| `browser.py`       | `BrowserTool` -- browser automation via CDP (Chrome DevTools Protocol). Multi-tab architecture allows concurrent use by main agent and subagents. |
| `http_client.py`   | `HttpClientTool` -- full HTTP client with download/upload support, content type mapping, and `PathResolver` integration. Supports GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS. |
| `rss.py`           | `RssReaderTool` -- read RSS 2.0 and Atom feeds. Auto-detects feed format, strips HTML from summaries. |
| `image.py`         | `ImageGenerationTool` -- generate images via configurable provider/model. |
| `twitter.py`       | `TwitterTool` -- post tweets on Twitter/X with OAuth 1.0a authentication. Supports text, media, and threads. |

**Subagent tool restrictions:** When `SubagentManager` builds a tool registry for a subagent, it includes file operations, shell, web tools, HTTP client, RSS reader, browser, image generation, and Twitter posting. It excludes `MessageTool`, `SpawnTool`, `CronTool`, and `SaveMemoryTool` to prevent subagents from sending messages to users, spawning further subagents, creating scheduled jobs, or modifying memory.

### Tasks

**Location:** `openbotx/tasks/`

Tasks provide observability into what the agent is doing.

| File          | Purpose                                                                             |
| ------------- | ----------------------------------------------------------------------------------- |
| `models.py`   | `Task` dataclass with fields: `id`, `title`, `description`, `state`, `agent_type`, `agent_name`, `parent_task_id`, `subagent_ids`, `result`, `error`, `created_at`, `updated_at`. |
| `manager.py`  | `TaskManager` -- creates tasks, tracks state transitions, and broadcasts `task:created` / `task:updated` events via the EventDispatcher. |

Task states follow a Kanban model:

| State   | Meaning                                    |
| ------- | ------------------------------------------ |
| `TODO`  | Task created, not yet started              |
| `DOING` | Agent is actively working on the task      |
| `DONE`  | Task completed successfully                |
| `ERROR` | Task failed with an error                  |

Tasks support a parent-child relationship: subagent tasks reference their `parent_task_id`, enabling hierarchical task tracking.

**Retention:** The `GET /api/tasks` endpoint excludes `DONE` and `ERROR` tasks older than 24 hours, keeping the task board focused on recent activity.

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
| `service.py`  | `CronService` -- runs a background tick loop (every 5 seconds), checks for due jobs, and fires them by publishing an `InboundMessage` to the message bus with `channel="cron"` and a unique `chat_id` per execution (`cron-{job_id}-{hex}`). Persists jobs to `workspace/cron_jobs.json`. |
| `types.py`    | Data classes: `CronJob`, `CronSchedule` (kinds: `at`, `every`, `cron`), `CronPayload` (message, channel, recipient), `CronJobState` (next/last run, run count, errors), `CronStore`. |

Schedule kinds:

| Kind    | Description                                            |
| ------- | ------------------------------------------------------ |
| `at`    | One-time execution at a specific timestamp (ms)        |
| `every` | Recurring at a fixed interval (ms)                     |
| `cron`  | Standard cron expression (requires `croniter` package) |

Jobs marked `delete_after_run: true` are automatically removed after their first execution.

### Heartbeat

**Location:** `openbotx/heartbeat/`

The heartbeat service periodically checks `HEARTBEAT.md` in the workspace for tasks.

| File         | Purpose                                                                            |
| ------------ | ---------------------------------------------------------------------------------- |
| `service.py` | `HeartbeatService` -- runs a background loop that reads `workspace/HEARTBEAT.md` every N seconds. If the file has actionable content (not just headers/comments), publishes an `InboundMessage` to the bus with `channel="heartbeat"` and `chat_id="heartbeat"` (session key: `heartbeat:heartbeat`). The agent processes the tasks in a dedicated session. Responses are routed to the WebSocket (since there is no dedicated heartbeat channel handler). |

Unlike cron (agent-managed via tools), `HEARTBEAT.md` is a file the user edits manually — a persistent to-do list the agent checks periodically.

### Config

**Location:** `openbotx/config/`

Configuration is defined as Pydantic models and loaded from YAML.

| File          | Purpose                                                                          |
| ------------- | -------------------------------------------------------------------------------- |
| `schema.py`   | Pydantic models: `Config`, `BotConfig`, `ServerConfig`, `AgentConfig`, `ModelParams`, `ImageConfig`, `AuthConfig`, `ProviderConfig`, `ChannelsConfig`, `TelegramConfig`, `ToolsConfig`, `GeneralToolsConfig`, `WebSearchConfig`, `ExecToolConfig`, `TwitterConfig`, `StorageConfig`, `HeartbeatConfig`, `CronConfig`, `ClassifierConfig`. |
| `loader.py`   | `load_config()` reads YAML and expands `${ENV_VAR}` patterns. `save_config()` writes the config back to YAML. |

Key configuration sections:

| Section      | Controls                                                     |
| ------------ | ------------------------------------------------------------ |
| `bot`        | Name and description                                         |
| `server`     | Host, port, and public URL                                   |
| `agents`     | Named agent configs (model, workspace, description, instructions, tools, params) |
| `auth`       | Username, password, JWT secret                               |
| `providers`  | API keys, base URLs, headers, and options per provider       |
| `channels`   | Telegram settings, progress/tool hint broadcasting           |
| `tools`      | General settings (workspace restriction), exec settings (timeout), web search API key, Twitter credentials |
| `storage`    | Backend type (local/S3), paths, credentials                  |
| `image`      | Image generation provider, model, API key                    |
| `heartbeat`  | Enabled flag, check interval                                 |
| `cron`       | Enabled flag                                                 |
| `classifier` | Model override for the agent classifier                      |

**AgentConfig** includes:

- `resolve_workspace(project_path)` method that resolves the workspace path relative to the project root.
- `@field_validator("workspace")` that defaults empty or null values to `"./workspace"`.
- `description` field used by the `AgentClassifier` for routing decisions.
- `instructions` field appended to the system prompt as agent-specific instructions.
- `tools` list that whitelists which tools are available to the agent.

### Helpers

**Location:** `openbotx/helpers/`

Utility modules shared across the codebase.

| File               | Purpose                                                                         |
| ------------------ | ------------------------------------------------------------------------------- |
| `path.py`          | `PathResolver` -- resolves file paths against a workspace directory and enforces allowed directory restrictions. Supports relative and absolute paths, home directory expansion (`~`), and multi-directory allowlists (workspace + public). Used by all file-based tools and the HTTP client. Also provides `media_path(filename)` -- generates date-organized storage paths (`public/media/YYYY/MM/DD/filename`), used by `ImageGenerationTool` and `TelegramChannel`. |
| `transcription.py` | Audio transcription via faster-whisper. Lazy-loads the Whisper model on first use. |
| `text.py`          | `humanize()` -- converts tool names to human-readable format. `describe_tool_use()` -- generates human-readable descriptions of tool calls for WebSocket events. |
| `config.py`        | Configuration helper utilities.                                                  |

### Storage

**Location:** `openbotx/storage/`

Pluggable storage backends for workspace files. The `StorageProvider` abstraction supports both file and directory operations, allowing the Files API and other components to work uniformly across all backends.

| File        | Purpose                                                |
| ----------- | ------------------------------------------------------ |
| `base.py`   | Abstract `StorageProvider` interface and `DirEntry` dataclass. Defines methods for file I/O (`read`, `write`, `delete`, `list`, `exists`, `size`) and directory operations (`list_dir`, `create_dir`, `delete_dir`, `is_directory`). |
| `local.py`  | Local filesystem storage. Uses `Path` operations and `shutil.rmtree` for recursive directory deletion. |
| `s3.py`     | AWS S3 storage backend. Uses `list_objects_v2` with `Delimiter` for directory listing, paginated batch deletion for directories. |

### Web Client

**Location:** `webclient/`

The web client is a single-page application built with:

- **Vue 3** -- component framework
- **Vite** -- build tool and dev server
- **PrimeVue 4** -- UI component library
- **Tailwind CSS 4** -- utility-first styling
- **Pinia** -- state management
- **md-editor-v3** -- Markdown editor and preview
- **WebSocket** -- real-time communication with the server

Pages:

| Page       | Function                                        |
| ---------- | ----------------------------------------------- |
| Chat       | Main conversation interface with session list panel, real-time updates, and session-aware message filtering. Users can switch between sessions (including heartbeat). Supports media attachments (images, audio files) and microphone audio recording. Audio files are transcribed via faster-whisper before being sent to the LLM. Links in messages open in a new tab. Agent messages display the agent name with an icon when multi-agent is active. |
| TaskBoard  | Kanban board showing tasks in TODO/DOING/DONE/ERROR columns. Task cards display duration, channel, error details, result preview, and real-time active tool status (spinner + tool name + description) for DOING tasks. Clicking a task title opens a confirmation dialog to navigate to the associated chat session. |
| Files      | File manager with type-aware rendering: `MarkdownEditor` (md-editor-v3) for `.md` files, `TextEditor` (monospace textarea) for other text files, `MediaPreview` (HTML5 img/video/audio) for media, and `FileDownload` for binary files. Supports creating files, creating folders, uploading files (to root or selected folder), deleting files/folders with confirmation dialogs, and a refresh button to force-reload the file tree. |
| Skills     | View agent skills in a card grid. Each card shows the skill name, description, and tags for "always active" (when applicable) and source origin ("builtin" or "project"). Clicking a card opens a dialog with the full skill content rendered as Markdown. Project skills can be edited directly — an Edit button switches to a raw textarea editor with Save/Cancel actions. Builtin skills remain read-only. |
| Tools      | View registered tools in a card grid. Each card shows the tool name and description. Clicking a card opens a dialog with the tool's parameter schema: parameter name, type, required status, description, enum values, and numeric ranges. |
| Scheduler  | Manage cron jobs                                |
| Settings   | Platform configuration with tabs: Bot, Channels (Telegram start/stop and config), Storage, Tools, Auth, and Advanced (YAML editor with validation and confirmation dialogs). Providers and agents are managed via the Advanced YAML editor. |
| Login      | Authentication                                  |

---

## Package Structure

```
openbotx/
├── agent/           # AI agent loop, orchestration, classification, context, memory, skills, subagents
│   ├── orchestrator.py    # Orchestrator - message routing to agents
│   ├── classifier.py      # AgentClassifier - LLM-based agent selection
│   ├── loop.py            # AgentLoop - main agentic processing loop
│   ├── context.py         # ContextBuilder - system prompt assembly
│   ├── memory.py          # MemoryStore - conversation memory persistence
│   ├── skills.py          # SkillsLoader - SKILL.md discovery and loading
│   └── subagent.py        # SubagentManager - background task delegation
├── bus/             # Async message bus and event dispatching
│   ├── queue.py         # MessageBus with inbound/outbound queues
│   ├── events.py        # InboundMessage, OutboundMessage data classes
│   └── dispatcher.py    # EventDispatcher - protocol-based event broadcasting
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
├── heartbeat/       # Periodic HEARTBEAT.md checker
│   └── service.py       # HeartbeatService - reads workspace/HEARTBEAT.md
├── helpers/         # Utility modules
│   ├── path.py          # PathResolver - workspace-scoped path resolution and directory restrictions
│   ├── transcription.py # Audio transcription via faster-whisper
│   ├── text.py          # Text formatting utilities (humanize, describe_tool_use)
│   └── config.py        # Configuration helper utilities
├── providers/       # LLM provider abstraction
│   ├── base.py          # LLMProvider and LLMResponse
│   ├── litellm_provider.py  # LiteLLM wrapper for multi-provider access
│   └── registry.py      # ProviderSpec definitions and matching
├── server/          # FastAPI server
│   ├── app.py           # ServerFactory, lifespan, and create_app
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
│   └── manager.py       # TaskManager with event broadcasting
├── tools/           # Built-in tool implementations
│   ├── base.py          # Abstract Tool class
│   ├── registry.py      # ToolRegistry - registration and execution
│   ├── filesystem.py    # read_file, write_file, edit_file, list_dir (PathResolver)
│   ├── shell.py         # exec (shell command execution)
│   ├── web.py           # web_search, web_fetch
│   ├── message.py       # message (send to channels)
│   ├── spawn.py         # spawn (delegate to subagent)
│   ├── cron.py          # cron (manage scheduled jobs)
│   ├── memory_tool.py   # save_memory (persist to MEMORY.md/HISTORY.md)
│   ├── browser.py       # browser (CDP-based browser automation)
│   ├── http_client.py   # http_client (HTTP requests with download/upload)
│   ├── rss.py           # rss_reader (RSS/Atom feed reader)
│   ├── image.py         # image_generation (AI image generation)
│   └── twitter.py       # twitter_post (Twitter/X posting with OAuth 1.0a)
└── version.py       # Package version
```

---

## Startup Lifecycle

The FastAPI lifespan context manager in `app.py` orchestrates the full startup sequence. The `ServerFactory` class handles all dependency creation.

```
1. Load configuration from YAML
2. Create ServerFactory from config
3. Ensure system workspace directory exists
4. Setup logging (rotating file handler + console)
5. Generate JWT secret if not configured
6. Initialize services:
   a. WebSocketManager + EventDispatcher (dispatcher wraps ws_manager)
   b. MessageBus
   c. SessionManager
   d. TaskManager (with EventDispatcher reference)
   e. SkillsLoader
   f. CronService (with callback that publishes to inbound queue)
   g. Create public directory structure (public/media/, public/documents/)
   h. Create Storage backend (local or S3)
   i. Orchestrator (via ServerFactory.create_orchestrator):
      - For each agent in config:
        1. Create LiteLLMProvider for the agent's model
        2. Resolve agent workspace path (AgentConfig.resolve_workspace)
        3. Create workspace directory
        4. Create PathResolver with allowed_dirs = [workspace, public_dir]
        5. Create SubagentManager with PathResolver
        6. Create AgentLoop with PathResolver, tools, and per-agent config
      - If multiple agents: create AgentClassifier
      - Return Orchestrator wrapping all agents
   j. ChannelManager (initializes Telegram if enabled)
   k. HeartbeatService
7. Start background tasks:
   a. Orchestrator.run() -- consumes inbound queue, routes to agents
   b. CronService.run() -- tick loop for scheduled jobs
   c. ChannelManager.start() -- starts channels + outbound dispatch
   d. HeartbeatService.start() -- periodic HEARTBEAT.md check
8. Re-queue recovered tasks (DOING → TODO on restart)
9. Application is ready to serve requests
```

On shutdown, the reverse occurs: HeartbeatService stops, orchestrator stops (which stops all agent loops and cleans up browser), cron service stops, and channels are shut down (with a 10-second timeout per channel). Tasks that are in DOING state when the server stops will be recovered on the next startup.

---

## Key Design Decisions

**Message bus decoupling.** Channels and the agent never communicate directly. The `MessageBus` with its two async queues provides a clean separation of concerns. This makes it straightforward to add new channels without modifying the agent, and allows the agent to process messages at its own pace.

**Multi-agent orchestration.** All messages from all channels funnel into one `Orchestrator` instance. When multiple agents are configured, the `AgentClassifier` uses an LLM call to determine which agent is best suited for each message based on agent descriptions and recent conversation history. Each agent has its own `AgentLoop` with independent workspace, model, tools, and `PathResolver`. Session isolation is achieved through the session key (`channel:chat_id`), not through separate agent instances.

**Per-agent workspace isolation.** Each agent gets its own workspace directory (resolved from its config via `AgentConfig.resolve_workspace()`). When `tools.general.restrict_to_workspace` is enabled, the `PathResolver` restricts file access to the agent's workspace and the shared public directory. This prevents agents from accessing each other's workspaces or the project root.

**Subagents for parallelism.** When the main agent needs to delegate work, it spawns a subagent via the `SpawnTool`. Subagents run as independent `asyncio.Task` instances with their own tool registries and iteration limits. They share the parent agent's `PathResolver` (same workspace access). They report results back through the inbound queue, which the main agent picks up in a subsequent turn.

**PathResolver as single source of truth.** All file path resolution and directory restriction enforcement is centralized in the `PathResolver` class (`openbotx/helpers/path.py`). Tools receive a `PathResolver` instance at construction and use it for all path operations. This eliminates duplication and ensures consistent behavior across all file-based tools.

**Memory consolidation.** Rather than sending the entire conversation history to the LLM every time, `MemoryStore` triggers a consolidation pass when unconsolidated messages exceed the `memory_window` threshold. A separate LLM call summarizes the conversation into `MEMORY.md` (long-term facts) and `HISTORY.md` (timestamped summaries).

**Markdown-based skills.** Skills are defined as `SKILL.md` files with YAML frontmatter. This makes them easy to author, version, and share. Skills marked `always: true` are automatically included in every system prompt. Others are listed in a summary block so the agent can request them when relevant.

**Tool error recovery.** The `ToolRegistry` appends a hint (`[Analyze the error above and try a different approach.]`) to any tool execution error. This nudges the LLM toward self-correction rather than repeating the same failed action.

**YAML configuration with env var expansion.** The config loader supports `${ENV_VAR}` patterns in YAML values, allowing sensitive values (API keys) to be injected from the environment without being stored in configuration files.

**ServerFactory pattern.** All dependency creation logic is encapsulated in the `ServerFactory` class, keeping the lifespan function clean and making the initialization sequence testable. The factory creates providers, storage, cron callbacks, and the full orchestrator graph from a single `Config` object.
