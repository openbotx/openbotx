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
  - [Credentials](#credentials)
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
| `chat:typing`        | `{ chat_id, agent_name, task_id }`                       | Agent is processing (show typing indicator)        |
| `chat:thinking`      | `{ task_id, chat_id, content, agent_name }`              | Streaming reasoning/thinking text                  |
| `chat:stream`        | `{ task_id, chat_id, content, agent_name }`              | Streaming content tokens in real time              |
| `chat:stream_end`    | `{ task_id, chat_id, agent_name }`                       | End of streaming response                          |
| `chat:tool_use`      | `{ task_id, chat_id, tool, description, agent_name }`    | Tool invocation with human-readable description    |
| `chat:message`       | `{ content, chat_id, task_id, agent_name }`                  | Final response — `content` is a block array      |
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
| `app.py`            | `ServerFactory` builds all server dependencies from config. `lifespan()` initializes and tears down all services. `create_app()` registers routers, middleware, WebSocket, and SPA fallback. |
| `websocket.py`      | `WebSocketManager` maintains active connections and broadcasts JSON events. `websocket_endpoint` handles auth and bidirectional communication. |
| `auth.py`           | JWT-based `AuthMiddleware`. Protects all `/api/*` routes except `/api/auth/login`. |
| `routes/auth.py`    | Login endpoint. Issues JWT tokens. |
| `routes/chat.py`    | Chat API. Send messages, list and manage sessions. |
| `routes/tasks.py`   | Task CRUD and state management. |
| `routes/files.py`   | File API with tree listing, read, download, create, write, and delete. Uses `StorageProvider` for all operations. Classifies files as `text`, `image`, `video`, `audio`, or `binary`. |
| `routes/skills.py`  | List, load, and update skills. PUT validates source is not builtin. |
| `routes/tools.py`   | List registered tools with their definitions. |
| `routes/channels.py`| Channel status, configuration, and start/stop control. Persists `enabled` state for auto-start on boot. |
| `routes/providers.py`    | Provider listing and configuration. |
| `routes/credentials.py`  | Credential CRUD (list, create, update, delete). |
| `routes/forms.py`    | Dynamic form schema endpoint for the frontend DynamicForm component. |
| `routes/scheduler.py`| Cron job management API. |
| `routes/config.py`  | Read and update platform configuration. Supports YAML export, validation, and service restart. |
| `routes/system.py`  | System info endpoint (`GET /system/info`). Returns OS, CPU, memory, disk, GPU, Python version, and OpenBotX version. |
| `routes/agents.py`  | Agent listing and configuration. |

**ServerFactory** encapsulates all dependency creation:

| Method                  | Purpose                                                                              |
| ----------------------- | ------------------------------------------------------------------------------------ |
| `create_provider(model)` | Resolves the model to a provider config, then resolves the credential for the API key, and creates a `LiteLLMProvider`. |
| `create_storage(url)`   | Creates `S3Storage` or `LocalStorage` based on the config.                           |
| `create_cron_callback(bus)` | Returns a callback that publishes `InboundMessage` to the bus when a cron job fires. |
| `create_orchestrator(...)` | Receives a shared `ProjectContext`. Merges provider-level `model_params` into each agent via dict merge (agent keys take precedence). Builds one `AgentLoop` per agent, creates `SubagentManager`s, and the `AgentClassifier`. Returns an `Orchestrator` that routes messages. |
| `setup_logging(path)`   | Configures rotating file handler + console handler for the `openbotx` logger.        |

The built web client (`openbotx/web_client/`) is served as a SPA at `/app/` with a catch-all fallback to `index.html`. The build output lives inside the Python package and is included in the `.whl` distribution.

Files under the project's `public/` directory are served at `/public/{path}` without authentication. This allows media files (images, video, audio) to be embedded in HTML5 tags (`<img>`, `<video>`, `<audio>`) without needing auth headers.

### Message Bus

**Location:** `openbotx/bus/`

The `MessageBus` is the backbone of the platform. It holds two `asyncio.Queue` instances that fully decouple message producers (channels) from the consumer (orchestrator/agent loop).

| File            | Purpose                                                                                   |
| --------------- | ----------------------------------------------------------------------------------------- |
| `queue.py`      | `MessageBus` with `inbound` and `outbound` async queues. Provides `publish_*` / `consume_*` methods. |
| `events.py`     | Message data classes: `InboundMessage` (channel -> agent) and `OutboundMessage` (agent -> channel). |
| `dispatcher.py` | `EventDispatcher` provides protocol-based event broadcasting. Components call `dispatcher.broadcast(event, data)` instead of coupling directly to WebSocketManager. Handlers register via `add_handler()`. |
| `command_queue.py` | `CommandQueue` — lane-based async task queue for concurrent message processing. Each lane (keyed by session key) has its own FIFO queue with configurable concurrency. A global `asyncio.Semaphore` caps total parallel tasks across all lanes. See [concurrency.md](concurrency.md). |

**Session key derivation:** Each `InboundMessage` derives its session key as `{channel}:{chat_id}`, which ties all messages from the same chat to the same conversation session. This can be overridden via `session_key_override`.

### Agent

**Location:** `openbotx/agent/`

The agent subsystem is the intelligence layer of the platform.

| File              | Purpose                                                                                        |
| ----------------- | ---------------------------------------------------------------------------------------------- |
| `orchestrator.py` | `Orchestrator` consumes inbound messages from the bus and dispatches them via a `CommandQueue`. Messages to the same session are serialized (same lane), while messages to different sessions run in parallel up to `max_concurrent`. Routes to the appropriate agent via `AgentClassifier`, or directly to the default agent when only one exists. |
| `classifier.py`   | `AgentClassifier` is an LLM-based message classifier. Analyzes the user's message and recent history to select the best agent using a `route` tool call. Falls back to the first agent on error. Only instantiated when multiple agents are configured. |
| `loop.py`         | `AgentLoop` is the main agentic loop. Receives an `AgentConfig` and a `ProjectContext`, builds context, streams LLM responses via `_consume_stream()`, executes tool calls, and repeats until a plain text response or `max_iterations` (default 40) is reached. Includes context window management (automatic compaction), history limiting (pre-compaction trimming via `max_history`), loop detection (SHA256-based tool call hashing with a 10-signature window and global circuit breaker at 10 repeats), finish_reason propagation (handles `length` gracefully when LLM hits token limit), typing indicators (`chat:typing` events), and usage tracking. Streams `chat:typing`, `chat:stream`, `chat:stream_end`, `chat:thinking`, `chat:tool_use`, `chat:user_message`, and `chat:transcription` events. |
| `context.py`      | `ContextBuilder` assembles the system prompt from identity, runtime info (platform, Python version), channel guidance (web/telegram), response guidelines, available tool names, bootstrap files (`SOUL.md`, `USER.md`, `AGENTS.md`, `TOOLS.md`), persisted memory, always-on skills, a skills summary, the public URL, and agent-specific instructions. Provides helpers for building OpenAI-compatible message arrays with multimodal support (text + images). |
| `context_window.py` | Context window management. `estimate_tokens()` uses chars/4 heuristic. `MODEL_CONTEXT_LIMITS` maps model patterns to context sizes. `needs_compaction()` checks if usage exceeds 85% of the model limit. |
| `compaction.py`   | `compact_messages()` summarizes the oldest 40% of conversation via the LLM, preserving key identifiers and context. Inherits `model_params` from the parent agent (no hardcoded overrides). Handles dangling tool results and strips tool output to 2000 chars before summarization. |
| `usage.py`        | `UsageTracker` accumulates prompt/completion/total token counts across multiple LLM calls within a task. Persisted on the `Task.token_usage` field on completion. |
| `memory.py`       | `MemoryStore` reads and writes `MEMORY.md` and `HISTORY.md` in the workspace `memory/` directory. Provides consolidation prompts when unconsolidated messages exceed `memory_window`. Consolidation input includes only user/assistant text messages. |
| `skills.py`       | `SkillsLoader` discovers SKILL.md files from built-in (`openbotx/skills/`) and workspace (`workspace/skills/`) directories. Parses YAML frontmatter for metadata (name, description, always, requires). Each skill is tagged with `source` (`"builtin"` or `"project"`) and `location` (absolute path). Skills marked `always: true` are injected into every system prompt if their requirements are satisfied. |
| `subagent.py`     | `SubagentManager` spawns independent background agent loops for delegated tasks. Uses `denied_tools=SUBAGENT_DENIED` to block `message`, `spawn`, `cron`, `exec`, `browser`, and memory tools. Subagents run with a minimal system prompt (identity, workspace paths, available tool names, concise guidelines) to save tokens. They have a lower iteration cap (15) and inherit the parent agent's `model_params`. Includes context window management (compaction) and history limiting. On completion, results are announced back to the main agent via the inbound queue. |

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

**Inter-agent communication:**

Agents do not communicate directly with each other. There is no message passing, shared queue, or RPC mechanism between agents. Each inbound message is routed to exactly one agent by the classifier, and only that agent processes it.

The only form of "communication" is indirect through the shared session history. All agents in the same chat use the same session (keyed by `{channel}:{chat_id}`). When the classifier switches from one agent to another, the new agent sees the full conversation history, including everything the previous agent said.

Example with two agents (`crypto` and `assistant`):

```
1. User: "What is the current price of Bitcoin?"
   → Classifier selects "crypto" (matches topic)
   → crypto agent responds with market data
   → Response saved to session history

2. User: "Thanks, now help me write an email"
   → Classifier detects topic change, selects "assistant"
   → assistant agent receives the full session history,
     including the crypto agent's previous response
   → assistant agent responds about the email
   → Response saved to session history

3. User: "Compare that price with Ethereum"
   → Classifier sees crypto context returning, selects "crypto"
   → crypto agent sees the entire conversation (its own earlier
     response + the assistant's email response + the new message)
   → crypto agent responds with the comparison
```

Each agent is unaware that other agents exist. They just see a conversation history with user and assistant messages. The classifier is the only component that knows about all agents and decides which one handles each turn.

**Orchestrator error resilience:**

The orchestrator's `run()` loop catches exceptions per-message. If a single message fails (e.g., the agent loop throws), the error is logged but the orchestrator continues processing the next message. This prevents one bad request from crashing the entire system. The 1-second timeout on `consume_inbound()` allows the stop event to be checked regularly for graceful shutdown.

**Agentic loop detail:**

```
1. Receive InboundMessage from Orchestrator (dispatched via CommandQueue lane)
2. Create or resume Task (set state to DOING)
3. Initialize task.live_state = {tool_uses: [], agent_name: ...}
4. Load or create Session
5. Initialize session.live_state = {tool_uses: [], agent_name: ...}
6. Create RequestContext (channel, chat_id, task_id, agent_name, message_id)
7. Build system prompt (ContextBuilder)
8. Build message array (system + history + new user message)
9. Loop:
   a. Increment task.iteration_count
   b. Trim history if max_history > 0 (drop orphaned tool results)
   c. Compact context if approaching model limit
   d. Broadcast chat:typing event
   e. Call LLM provider with messages + tool definitions
   f. If response contains tool_calls:
      - Execute each tool via ToolRegistry (with RequestContext)
      - Increment task.tool_count per tool call
      - Broadcast chat:tool_use via EventDispatcher
      - Append tool entry to session.live_state and task.live_state
      - Accumulate content blocks (text and tool_use blocks)
      - Append assistant message + tool results to messages
      - Continue loop
   g. If response is plain text:
      - Break loop, return response text and content blocks
10. Clear session.live_state and task.live_state
11. Save assistant message with content blocks array to session
12. Publish OutboundMessage to bus
13. Set Task state to DONE
14. Check if memory consolidation is needed
```

### Channels

**Location:** `openbotx/channels/`

Channels are the communication endpoints that connect users to the platform.

| File           | Purpose                                                                                  |
| -------------- | ---------------------------------------------------------------------------------------- |
| `base.py`      | `BaseChannel` abstract interface. Defines `start()`, `stop()`, `send()`, and `is_running`. |
| `manager.py`   | `ChannelManager` receives `credentials` dict at construction. Initializes channels from config, resolving credentials through credential references. Runs an outbound dispatch loop and routes messages. `start_channel()` recreates the channel from current config and credentials, enabling credential changes without restart. Web messages go through `WebSocketManager`. External channels use their own implementations. |
| `telegram.py`  | `TelegramChannel` integrates with Telegram via `python-telegram-bot`. Supports allowed user filtering, proxy configuration, and reply-to-message mode. |

The web channel is implicit and does not have a `BaseChannel` implementation. The WebSocket endpoint handles web client communication directly. `ChannelManager._route_message` broadcasts web-bound outbound messages via `WebSocketManager`.

### Credentials

Credentials centralize all secrets in one place. Each credential has a `type` (e.g., `simple`, `oauth1`, `basic`, `login`, `aws`) and type-specific fields. Other configuration sections reference credentials by name via their `credential` field, rather than storing secrets directly.

The `CredentialConfig` model serializes only the fields relevant to its `type`, keeping the stored configuration clean.

### Providers

**Location:** `openbotx/providers/`

The provider subsystem abstracts LLM access behind a uniform interface.

| File                   | Purpose                                                                             |
| ---------------------- | ----------------------------------------------------------------------------------- |
| `base.py`              | `LLMProvider` abstract class, `LLMResponse` data class (content, tool_calls, reasoning_content, error_type, has_tool_calls), and `StreamChunk` data class for streaming responses. Default `chat_stream()` falls back to non-streaming `chat()`. |
| `litellm_provider.py`  | `LiteLLMProvider` wraps [LiteLLM](https://github.com/BerriAI/litellm) for multi-provider LLM access. Handles model name resolution, environment variable setup, prompt caching, tool call ID sanitization, transcript validation (message ordering), thinking/reasoning budget, and streaming. Uses shared `_build_kwargs()` for both `chat()` and `chat_stream()`. |
| `registry.py`          | `PROVIDERS` tuple of `ProviderSpec` objects. Defines metadata for each supported provider (custom, openrouter, anthropic, openai, deepseek, gemini, groq) with keyword matching and API key detection. |
| `errors.py`            | Error classification system. `LLMErrorType` enum, typed exception hierarchy (`ContextOverflowError`, `RateLimitError`, `BillingError`, `AuthError`, `TransientError`), and `classify_error()` for pattern-based error classification. |
| `retry.py`             | `retry_with_backoff()` wraps LLM calls with exponential backoff retry (3 attempts, 1-30s delay). Only retries `RateLimitError` and `TransientError`; other errors propagate immediately. |

**Provider resolution:** The `Config.get_provider()` method matches a model name to a provider by first checking the LiteLLM-style prefix (e.g., `anthropic/claude-sonnet-4-20250514`), then falling back to keyword matching, and finally returning any provider whose referenced credential has an API key configured. `ServerFactory.create_provider()` resolves through provider -> credential -> concrete key to build a `LiteLLMProvider`.

**Provider-level `model_params`:** Each `ProviderConfig` can define a default `model_params` dict (arbitrary key-value pairs like `max_tokens`, `temperature`, `top_p`, etc.). At startup, `ServerFactory.create_orchestrator` merges provider defaults into each agent's `model_params` using simple dict merge (`{**provider_params, **agent_params}`). Agent-level keys always take precedence.

**Error handling:** LLM errors are classified by pattern matching on the error message. Context overflow errors propagate as `ContextOverflowError` so the agent loop can compact and retry. Rate limit and transient errors are retried with exponential backoff. Terminal errors (billing, auth) propagate immediately. Unknown errors are returned as `LLMResponse` with `finish_reason="error"`.

### Tools

**Location:** `openbotx/tools/`

Tools are the actions the agent can perform in the world.

| File               | Purpose                                                                  |
| ------------------ | ------------------------------------------------------------------------ |
| `base.py`          | Abstract `Tool` class with `name`, `description`, `parameters`, `execute()`, `validate_params()`, and `to_schema()`. |
| `context.py`       | `RequestContext` — immutable (frozen) dataclass carrying per-request metadata (channel, chat_id, task_id, agent_name, message_id). Created once per `process_message` call and injected into tool execution via `kwargs["_context"]`. Replaces the previous mutable `set_context()` pattern, making concurrent message processing safe. |
| `registry.py`      | `ToolRegistry` manages tool registration, lookup, and execution. `execute()` accepts an optional `RequestContext` and injects it as `_context` into tool kwargs. Generates tool definition arrays for LLM calls. Appends error hints on failure to guide recovery. Applies context-aware tool result truncation (30% of context window, capped at 400K chars) to prevent context overflow. `build_registry()` supports `denied_tools` parameter for filtering. |
| `filesystem.py`    | `ReadFileTool`, `WriteFileTool`, `EditFileTool`, `ListDirTool` -- file operations using `PathResolver` for path resolution and directory restriction enforcement. |
| `shell.py`         | `ExecTool` executes shell commands with configurable timeout and optional workspace restriction. |
| `web.py`           | `WebSearchTool` (Brave Search API), `WebFetchTool` (HTTP fetch + content extraction). |
| `message.py`       | `MessageTool` sends messages to channels from within the agent loop. Reads channel/chat_id from `RequestContext` (via `kwargs["_context"]`). |
| `spawn.py`         | `SpawnTool` delegates tasks to background subagents. Reads origin channel/chat_id/task_id from `RequestContext`. |
| `cron.py`          | `CronTool` creates, lists, and removes scheduled jobs. Reads channel/chat_id from `RequestContext`. |
| `memory_tool.py`   | `MemorySaveTool` persists content to MEMORY.md and HISTORY.md. `MemoryReadTool` reads them on demand. `MemorySearchTool` searches across memory files with context. |
| `browser.py`       | `BrowserTool` provides browser automation via CDP using the vendored `openbotx/cdp/` library. A singleton `_ChromeInstance` manages the Chrome process. Each tool instance gets its own tab. Clicks use pure CDP: resolve element, scroll into view, get content quads, dispatch mouse events. |
| `http_client.py`   | `HttpClientTool` is a full HTTP client with download/upload support, `PathResolver` integration, and authentication via credentials (OAuth 1.0a, Basic, Bearer). |
| `rss.py`           | `RssReaderTool` reads RSS 2.0 and Atom feeds. Auto-detects format and strips HTML from summaries. |
| `image.py`         | `ImageGenerationTool` generates images with provider-routed backends. Gemini models use the Google GenAI SDK with native aspect ratio, resolution, reference images, and search grounding. Other models use litellm. |

**Subagent tool restrictions:** When `SubagentManager` builds a tool registry for a subagent, it passes `denied_tools=SUBAGENT_DENIED` (a hardcoded set: `spawn`, `message`, `memory_save`, `memory_read`, `memory_search`, `cron`, `exec`, `browser`) to `build_registry()`. This is combined with the agent's own `denied_tools` config field. The result is subagents have file operations, web tools, HTTP client, RSS reader, and image generation — but cannot execute shell commands, automate browsers, send messages, spawn further subagents, create scheduled jobs, or modify memory.

### Tasks

**Location:** `openbotx/tasks/`

Tasks provide observability into what the agent is doing.

| File          | Purpose                                                                             |
| ------------- | ----------------------------------------------------------------------------------- |
| `models.py`   | `Task` dataclass with fields for identity, state, timing, metrics, relationships, and `token_usage` (cumulative prompt/completion/total tokens). `duration_ms` returns elapsed milliseconds from `started_at` to `completed_at` (or to now if still running). The `live_state` dict holds transient runtime data (e.g., `tool_uses`) that lives only in memory and is never persisted to JSONL. |
| `manager.py`  | `TaskManager` creates tasks, tracks state transitions, and broadcasts `task:created` / `task:updated` events. Auto-sets `started_at` on `DOING` and `completed_at` on `DONE`/`ERROR`. Provides `increment_tool_count()` and `increment_iteration_count()` for in-memory metric tracking. |

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
| `manager.py`  | `SessionManager` manages `Session` objects stored as JSONL files in `workspace/sessions/`. Each session is keyed by `{channel}_{chat_id}`. Provides `get_or_create`, `save` (async with per-session write lock), `delete`, and `list_sessions`. Uses an in-memory cache for fast access. |

The `Session` dataclass holds a list of messages (role + content + metadata) and tracks `last_consolidated` for memory consolidation. `get_history()` returns messages for building LLM context, capped at 500 by default. The transient `live_state` dict holds runtime data (e.g., `tool_uses`, `agent_name`) during execution. It is returned via the chat history API but never persisted to JSONL.

**Write lock:** `save()` is async and acquires a per-session `asyncio.Lock` before writing. This prevents concurrent requests to the same session from corrupting the JSONL file. Locks are created lazily per session key.

### Cron

**Location:** `openbotx/cron/`

The cron service enables scheduled task execution.

| File          | Purpose                                                                            |
| ------------- | ---------------------------------------------------------------------------------- |
| `service.py`  | `CronService` runs a background tick loop every 5 seconds. When a job is due, it publishes an `InboundMessage` with `channel="cron"` and a unique `chat_id` per execution. Persists jobs to `workspace/cron_jobs.json`. |
| `types.py`    | Data classes: `CronJob`, `CronSchedule` (kinds: `at`, `every`, `cron`), `CronPayload` (message, channel, recipient), `CronJobState` (next/last run, run count, errors). |

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
| `service.py` | `HeartbeatService` runs a background loop that reads `workspace/HEARTBEAT.md` every N seconds. If the file has actionable content, it publishes an `InboundMessage` with `channel="heartbeat"` and `chat_id="heartbeat"`. The agent processes the tasks in a dedicated session. Responses are routed to the WebSocket. |

Unlike cron (agent-managed via tools), `HEARTBEAT.md` is a file the user edits manually — a persistent to-do list the agent checks periodically.

### Config

**Location:** `openbotx/config/`

Configuration is defined as Pydantic models and loaded from YAML.

| File          | Purpose                                                                          |
| ------------- | -------------------------------------------------------------------------------- |
| `schema.py`   | Pydantic models for all configuration sections (`Config`, `AgentConfig`, `CredentialConfig`, `ProviderConfig`, `ToolsConfig`, etc.). |
| `loader.py`   | `load_config()` reads YAML and expands `${ENV_VAR}` patterns. `save_config()` writes the config back to YAML. |

Key configuration sections:

| Section           | Controls                                                     |
| ----------------- | ------------------------------------------------------------ |
| `bot`             | Name and description                                         |
| `server`          | Host, port, public URL, and JWT secret credential reference  |
| `agents`          | Named agent configs (model, workspace, description, instructions, tools, model_params, agent_params) |
| `credentials`     | Centralized credentials (simple keys/tokens, OAuth, Basic, AWS, web client login) |
| `providers`       | LLM provider configs (credential reference, request_headers, request_options, model_params) |
| `web_client`      | Web UI authentication (credential reference for login)       |
| `channels`        | Telegram settings (credential reference), progress/tool hint broadcasting |
| `tools`           | General settings (workspace restriction), exec settings (timeout), web search credential reference |
| `storage`         | Backend type (local/S3), paths, credential reference         |
| `image`           | Image generation model in `provider/model` format            |
| `heartbeat`       | Enabled flag, check interval                                 |
| `cron`            | Enabled flag                                                 |
| `classifier`      | Model override for the agent classifier                      |

**AgentConfig** includes:

- `resolve_workspace(project_path)` method that resolves the workspace path relative to the project root.
- `@field_validator("workspace")` that defaults empty or null values to `"./workspace"`.
- `description` field used by the `AgentClassifier` for routing decisions.
- `instructions` field appended to the system prompt as agent-specific instructions.
- `tools` list that whitelists which tools are available to the agent.
- `agent_params.max_history` (default 0 = no limit) trims the message history to N messages before the compaction check. This is a cheap pre-compaction optimization that avoids unnecessary LLM calls.
- `model_params.thinking` controls extended thinking budget: `"off"` (default), `"low"` (2048 tokens), `"medium"` (8192), `"high"` (32768). When enabled, temperature is forced to 1 (required by Anthropic).

### Helpers

**Location:** `openbotx/helpers/`

Utility modules shared across the codebase.

| File               | Purpose                                                                         |
| ------------------ | ------------------------------------------------------------------------------- |
| `path.py`          | `PathResolver` resolves file paths against a workspace directory and enforces allowed directory restrictions. Supports relative/absolute paths, `~` expansion, and multi-directory allowlists. Used by all file-based tools and the HTTP client. Also provides `media_path()` for date-organized storage paths (`public/media/YYYY/MM/DD/filename`). |
| `transcription.py` | Audio transcription via faster-whisper. Lazy-loads the Whisper model on first use. |
| `text.py`          | `humanize()` converts tool names to human-readable format. `describe_tool_use()` generates descriptions of tool calls for WebSocket events. |
| `oauth1.py`         | OAuth 1.0a signature generation (RFC 5849). `build_oauth1_header()` builds HMAC-SHA1 signed `Authorization` headers. Used by `HttpClientTool`. |
| `ssrf.py`          | SSRF protection. `validate_url()` blocks requests to private/internal networks. `ssrf_event_hook()` validates redirects. Used by `HttpClientTool`, `WebFetchTool`, and `RssReaderTool`. |
| `secrets.py`       | Sensitive value masking for config display. `is_sensitive_key()`, `mask_dict()`, `is_empty_or_blank()`. Used by config routes to hide API keys and passwords. |

### Storage

**Location:** `openbotx/storage/`

Pluggable storage backends for workspace files. The `StorageProvider` abstraction supports both file and directory operations, allowing the Files API and other components to work uniformly across all backends.

| File        | Purpose                                                |
| ----------- | ------------------------------------------------------ |
| `base.py`   | Abstract `StorageProvider` interface and `DirEntry` dataclass. Defines methods for file I/O and directory operations. |
| `local.py`  | Local filesystem storage. Uses `Path` operations and `shutil.rmtree` for recursive directory deletion. |
| `s3.py`     | AWS S3 storage backend. Uses `list_objects_v2` with `Delimiter` for directory listing, paginated batch deletion for directories. |

### Web Client

**Location:** `web_client/`

The web client is a single-page application built with:

- **Vue 3** for components
- **Vite** for build and dev server
- **PrimeVue 4** for UI components
- **Tailwind CSS 4** for styling
- **Pinia** for state management
- **md-editor-v3** for Markdown editing and preview
- **WebSocket** for real-time communication

Pages:

| Page       | Function                                        |
| ---------- | ----------------------------------------------- |
| Chat       | Main conversation interface with session list panel and real-time updates. Users can switch between sessions without losing streaming state (per-session live cache). Assistant messages render typed content blocks (text and tool_use) in order. A processing indicator (animated dots + "Processing..." label) shows at the bottom of live messages. Supports media attachments and microphone recording. Audio is transcribed via faster-whisper before being sent to the LLM. In multi-agent mode, messages display the agent name. |
| TaskBoard  | Kanban board with TODO/DOING/DONE/ERROR columns. Cards display duration, channel, errors, and result preview. DOING tasks show real-time tool status. Clicking a task title navigates to the associated chat session. |
| Files      | File manager with type-aware rendering. Uses `MarkdownEditor` for `.md` files, `TextEditor` for other text, `MediaPreview` for media, and `FileDownload` for binaries. Supports creating, uploading, and deleting files and folders. |
| Skills     | Card grid of agent skills. Each card shows name, description, source tag, and "always active" tag when applicable. Clicking a card opens the full content as Markdown. Project skills can be edited inline. Builtin skills are read-only. |
| Tools      | Card grid of registered tools. Clicking a card opens the parameter schema with types, required status, and descriptions. |
| Scheduler  | Manage cron jobs. |
| Settings   | Platform configuration driven by dynamic form schemas from `/api/forms`. Uses a `DynamicForm` component that replaces hardcoded forms. Tabs include: Info (OS, CPU, memory, disk, GPU, versions), Bot, Server, Web Client, Agents, Credentials, Providers, Channels, Storage, Tools, Image, and Advanced (YAML editor with validation). |
| Login      | Authentication. |

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
├── cdp/             # Vendored Chrome DevTools Protocol library (from python-cdp)
│   ├── base.py          # IEventLoop protocol
│   ├── exceptions.py    # CDP exception classes
│   ├── utils.py         # LoggerMixin, Retry, Worker utilities
│   ├── browser.py       # ChromeLauncher - Chrome process management
│   ├── connection.py    # CDPConnection, CDPSession, connect_cdp (WebSocket)
│   └── protocol/        # Auto-generated CDP domain modules (runtime, page, dom, input_, target, etc.)
├── bus/             # Async message bus, event dispatching, and command queue
│   ├── queue.py         # MessageBus with inbound/outbound queues
│   ├── command_queue.py # CommandQueue — lane-based concurrent task queue
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
│   ├── oauth1.py        # OAuth 1.0a signature generation (HMAC-SHA1)
│   ├── ssrf.py          # SSRF protection - blocks requests to private/internal networks
│   ├── transcription.py # Audio transcription via faster-whisper
│   ├── text.py          # Text formatting utilities (humanize, describe_tool_use)
│   └── secrets.py       # Sensitive value masking for config display
├── providers/       # LLM model provider abstraction
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
│   ├── memory_tool.py   # memory_save, memory_read, memory_search
│   ├── browser.py       # browser (CDP-based browser automation)
│   ├── http_client.py   # http_client (HTTP requests with auth profiles)
│   ├── rss.py           # rss_reader (RSS/Atom feed reader)
│   └── image.py         # generate_image (AI image generation)
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
5. Auto-create server.credential (simple, random key) if not configured; auto-create web_client credential (login, admin/admin) if not configured
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
      - Create ProjectContext (project paths, tool configs, storage) — shared across all agents
      - For each agent in config:
        1. Create LiteLLMProvider for the agent's model
        2. Resolve agent workspace path (AgentConfig.resolve_workspace)
        3. Create workspace directory
        4. Create SubagentManager with AgentConfig + ProjectContext
        5. Create AgentLoop with AgentConfig + ProjectContext (tool registration via build_registry())
      - If multiple agents: create AgentClassifier
      - Return Orchestrator wrapping all agents
   j. ChannelManager (receives credentials dict, initializes Telegram if enabled by resolving token from credential reference)
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

**Memory consolidation.** Rather than sending the entire conversation history to the LLM every time, `MemoryStore` triggers a consolidation pass when unconsolidated messages exceed the `memory_window` threshold. A separate LLM call (inheriting the parent agent's `model_params`) summarizes the conversation into `MEMORY.md` (long-term facts) and `HISTORY.md` (timestamped summaries).

**Markdown-based skills.** Skills are defined as `SKILL.md` files with YAML frontmatter. This makes them easy to author, version, and share. Skills marked `always: true` are automatically included in every system prompt. Others are listed in a summary block so the agent can request them when relevant.

**Tool error recovery.** The `ToolRegistry` appends a hint (`[Analyze the error above and try a different approach.]`) to any tool execution error. This nudges the LLM toward self-correction rather than repeating the same failed action.

**YAML configuration with env var expansion.** The config loader supports `${ENV_VAR}` patterns in YAML values, allowing sensitive values (API keys) to be injected from the environment without being stored in configuration files.

**Centralized credentials.** All credentials (API keys, OAuth tokens, passwords, AWS keys, bot tokens) are defined in a single `credentials` dictionary. Other configuration sections (providers, channels, tools, storage, web_client, server) reference credentials by name via their `credential` field. The server's JWT signing secret is also stored as a `simple` credential referenced by `server.credential`. This eliminates credential duplication and provides a single place to manage secrets.

**ServerFactory pattern.** All dependency creation logic is encapsulated in the `ServerFactory` class, keeping the lifespan function clean and making the initialization sequence testable. The factory creates providers, storage, cron callbacks, and the full orchestrator graph from a single `Config` object. `create_provider()` resolves through provider -> credential -> concrete key.

**Lane-based concurrency.** The `Orchestrator` dispatches messages via a `CommandQueue` with lanes keyed by session key. Messages to the same session are serialized (FIFO within a lane), while messages to different sessions run in parallel up to `max_concurrent` (default 1). A global `asyncio.Semaphore` caps total parallel tasks. This eliminates the previous bottleneck where one slow message blocked all others. See [concurrency.md](concurrency.md).

**Per-request tool context.** Tools that need request-scoped data (channel, chat_id, task_id) receive an immutable `RequestContext` via `kwargs["_context"]` instead of storing mutable state on shared tool instances. This replaces the previous `set_context()` pattern, which was unsafe for concurrent execution. The `ToolRegistry.execute()` method injects the context automatically.

**Typed content blocks.** Assistant messages store `content` as an array of typed blocks (`text`, `tool_use`) instead of a plain string. This preserves the natural interleaving of text and tool calls as they occur during the agent loop. The frontend renders blocks in order, showing text and tool indicators exactly where they appeared. User messages remain plain strings. The `ContextBuilder` normalizes block arrays back to plain text when building LLM context.

**Per-session live state cache.** The frontend chat store maintains a `_liveCache` Map keyed by `chat_id` that tracks streaming state (content blocks, agent name, tool running status) per session. WebSocket events always update their session's cache regardless of which session the user is viewing. When switching sessions, the client-side cache is preferred over backend `live_state`, preserving accumulated streaming content.
