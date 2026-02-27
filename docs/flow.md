# How OpenBotX Works

This document explains the complete execution flow of the OpenBotX AI agent, from the moment a user sends a message to the final response delivery. Each step follows the actual execution sequence of the system.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Server Startup](#2-server-startup)
3. [Configuration Loading](#3-configuration-loading)
4. [Authentication](#4-authentication)
5. [Message Entry](#5-message-entry)
6. [Message Bus](#6-message-bus)
7. [Message Processing](#7-message-processing)
8. [Context Building](#8-context-building)
9. [The .md Files](#9-the-md-files)
10. [Skills](#10-skills)
11. [Creating New Skills](#11-creating-new-skills)
12. [Agent Loop](#12-agent-loop)
13. [AI Provider Selection](#13-ai-provider-selection)
14. [Tools](#14-tools)
15. [Subagents](#15-subagents)
16. [Memory and Consolidation](#16-memory-and-consolidation)
17. [Sessions](#17-sessions)
18. [Task Management](#18-task-management)
19. [WebSocket](#19-websocket)
20. [Heartbeat Service](#20-heartbeat-service)
21. [Scheduler (Cron)](#21-scheduler-cron)
22. [Output Routing](#22-output-routing)
23. [Media Pipeline](#23-media-pipeline)
24. [Server Shutdown](#24-server-shutdown)
25. [Complete Cycle](#25-complete-cycle)

---

## 1. Overview

OpenBotX is an AI assistant platform that runs as a web server. When you start the system with `openbotx start`, a FastAPI server boots up and creates all the necessary components.

```mermaid
graph TD
    A[User - Browser / Telegram] -->|Sends message| B[Input Channel]
    B -->|WebSocket or Telegram| C[Message Bus - Inbound Queue]
    C --> D[Agent Loop]
    D -->|Queries| E[LLM - AI Model]
    D -->|Uses| F[Tools]
    F -->|Result| D
    E -->|Response| D
    D -->|Final response| G[Message Bus - Outbound Queue]
    G --> H[Channel Manager]
    H -->|WebSocket| A
    H -->|Telegram API| A
```

Everything is wired together in `openbotx/server/app.py`. The `ServerFactory` class handles dependency creation, and the `lifespan()` function orchestrates the startup/shutdown sequence.

---

## 2. Server Startup

When you run `openbotx start`, the CLI (`openbotx/cli/commands.py`) does the following:

1. Starts a Uvicorn (ASGI) server with the configured host and port (default: `0.0.0.0:8000`)
2. After 1.5 seconds, automatically opens the browser (unless `--no-browser` is passed):
   - If `server.public_url` is configured (e.g., `https://my-domain.com`), opens that URL
   - Otherwise, opens `http://localhost:{port}/app/`

The FastAPI server uses an async **lifespan** that manages the entire lifecycle. During startup, components are created in this order:

```mermaid
graph TD
    A[load_config] -->|Loads config.yml + .env| B[Create ServerFactory]
    B --> C[Create Workspace + Setup Logging]
    C --> D[Generate JWT Secret if needed]
    D --> E[Create WebSocketManager + EventDispatcher]
    E --> F[Create MessageBus]
    F --> G[Create SessionManager]
    G --> H[Create TaskManager]
    H --> I[Create SkillsLoader]
    I --> J[Create CronService]
    J --> K[Create public/ directory structure]
    K --> L[Create Storage backend]
    L --> M["ServerFactory.create_orchestrator()"]
    M --> M1["For each agent: Create Provider"]
    M1 --> M2["Resolve workspace + Create PathResolver"]
    M2 --> M3["Create SubagentManager + AgentLoop"]
    M3 --> M4["Create AgentClassifier (if multi-agent)"]
    M4 --> M5["Return Orchestrator"]
    M5 --> N[Create ChannelManager]
    N --> O[Create HeartbeatService]
    O --> P["Start Orchestrator (background task)"]
    P --> Q["Start CronService (background task)"]
    Q --> R["Start ChannelManager (channels + dispatch)"]
    R --> S["Start HeartbeatService (background task)"]
    S --> T[Re-queue recovered tasks]
    T --> U[Server ready]
```

The `ServerFactory` class encapsulates all dependency creation logic. It receives the `Config` object and provides methods to create providers, storage backends, cron callbacks, and the full orchestrator graph.

Each agent gets its own `AgentLoop` with:
- Its own `LiteLLMProvider` (configured for the agent's model)
- Its own workspace directory (resolved via `AgentConfig.resolve_workspace()`)
- Its own `PathResolver` with `allowed_dirs = [workspace, public_dir]`
- Its own `SubagentManager` (sharing the parent's `PathResolver`)
- Its own `ToolRegistry` (filtered by the agent's `tools` whitelist, if set)

After all services are started, the server re-queues any tasks that were interrupted by a previous shutdown. Tasks that were in the DOING state are reset to TODO during `TaskManager` initialization, and then published back to the MessageBus so the agent can re-execute them (see section 18).

---

## 3. Configuration Loading

The `load_config()` in `openbotx/config/loader.py` does the following:

1. **Loads `.env`**: Calls `load_dotenv()` to load environment variables from the `.env` file at the project root
2. **Reads `config.yml`**: Parses the YAML file with `yaml.safe_load()`
3. **Expands environment variables**: Substitutes `${VAR}` patterns with actual environment variable values, recursively across strings, dicts, and lists:

```yaml
# config.yml
providers:
  anthropic:
    api_key: ${ANTHROPIC_API_KEY}  # will be replaced with the actual value
```

4. **Validates with Pydantic**: The resulting dictionary is validated by the `Config` model (Pydantic), which applies defaults for missing fields

### Important Defaults

| Setting | Default |
|---|---|
| Server | `host: 0.0.0.0`, `port: 8000`, `public_url: ""` |
| Authentication | `username: admin`, `password: admin` |
| Model | `anthropic/claude-sonnet-4-20250514` |
| Model params | `max_tokens: 8192`, `temperature: 0.1` |
| Max iterations | `max_iterations: 40` |
| Memory window | `memory_window: 100` |
| Shell timeout | `exec.timeout: 60` seconds |
| Workspace restriction | `general.restrict_to_workspace: true` |
| WebSocket progress | `send_progress: true` |
| Tool hints | `send_tool_hints: false` |
| Heartbeat | `enabled: true`, `interval: 1800` (30 minutes) |

### Saving

`save_config()` uses `model_dump(exclude_defaults=True)` — meaning it only saves values that differ from defaults, keeping `config.yml` clean and minimal.

---

## 4. Authentication

The authentication system (`openbotx/server/auth.py`) uses **JWT (JSON Web Tokens)** to protect API routes.

```mermaid
sequenceDiagram
    participant U as User (Browser)
    participant S as Server

    U->>S: POST /api/auth/login {username, password}
    S->>S: Validate credentials
    S->>U: {token: "eyJ..."} (JWT valid for 24h)

    U->>S: GET /api/tasks (Header: Bearer eyJ...)
    S->>S: Verify JWT
    S->>U: [task list]

    U->>S: WebSocket /ws?token=eyJ...
    S->>S: Verify JWT via query param
    S->>U: Connection accepted
```

### Flow Details

1. **Login**: The user sends `POST /api/auth/login` with username and password. If valid, receives a JWT token signed with HS256, valid for **24 hours**
2. **API routes**: All routes under `/api/` require the `Authorization: Bearer {token}` header. The middleware extracts and validates the token
3. **WebSocket**: The token is passed as a query parameter (`/ws?token=...`) and validated before accepting the connection. If invalid, the connection is closed with code `4001`
4. **Public routes**: The following routes do not require authentication:
   - `/api/auth/login` and `/api/health` (public routes)
   - `/app/*` (static frontend)
   - `/ws` (authentication handled internally)

If no `secret_key` is configured in `config.yml`, the server automatically generates a random UUID as the secret on startup.

---

## 5. Message Entry

A message can enter the system through three paths:

### Via WebSocket (Browser)

1. The user opens the browser at `http://localhost:8000`
2. The Vue.js frontend connects via **WebSocket** at `/ws?token={jwt}`
3. When the user sends a message, the frontend sends a JSON event:

```json
{
  "type": "chat:send",
  "data": {
    "message": "Hello, how are you?",
    "session_id": "direct",
    "metadata": {}
  }
}
```

4. The `websocket_endpoint()` (`openbotx/server/websocket.py`) creates an `InboundMessage` and publishes it to the bus inbound queue:

```python
msg = InboundMessage(
    channel="web",
    sender_id="web_user",
    chat_id=session_id,
    content=content,
    metadata=data.get("data", {}).get("metadata", {}),
)
await bus.publish_inbound(msg)
```

### Via REST API

In addition to WebSocket, there is a REST route for sending messages:

```
POST /api/chat
{
  "message": "Hello",
  "session_id": "direct"
}
```

The route (`openbotx/server/routes/chat.py`) creates a task beforehand and injects the `task_id` into the message metadata. Returns `{"task_id": "abc123", "session_id": "direct"}` — the frontend can then track progress via WebSocket.

### Via Telegram

1. The `TelegramChannel` performs periodic **polling** on the Telegram API to fetch new messages
2. Upon receiving a message, it creates an `InboundMessage` with `channel="telegram"` and Telegram metadata (`user_id`, `username`, `first_name`, `is_group`, `message_id`)
3. If the message contains media (photos, documents), the file is downloaded to a date-organized subdirectory under `public/media/` (e.g., `public/media/2026/02/26/abc123.jpg`) and the **relative path** is added to the `media` list
4. The message is published to the same bus inbound queue

### InboundMessage Structure

In all cases, the message becomes an `InboundMessage` with these fields:

| Field | Description |
|---|---|
| `channel` | Source: `"web"`, `"telegram"`, `"cron"`, or `"heartbeat"` |
| `sender_id` | Who sent it (e.g., `"web_user"`, `"telegram_12345"`) |
| `chat_id` | Conversation identifier |
| `content` | Message text |
| `media` | List of attached file paths |
| `metadata` | Extra data (task_id, message_id, etc.) |
| `session_key` | Session key: `channel:chat_id` (e.g., `web:direct`) |
| `session_key_override` | If set, overrides the session key |

---

## 6. Message Bus

The Message Bus (`openbotx/bus/queue.py`) is the heart of the communication system. It works as an internal mailbox with two queues:

```mermaid
graph LR
    WEB[Web - WebSocket] -->|InboundMessage| IN[Inbound Queue]
    TEL[Telegram] -->|InboundMessage| IN
    CRON[Cron Service] -->|InboundMessage| IN
    IN --> AGENT[Agent Loop]
    AGENT -->|OutboundMessage| OUT[Outbound Queue]
    OUT --> CM[Channel Manager]
    CM -->|WebSocket| WEB2[Browser]
    CM -->|Telegram API| TEL2[Telegram]
```

```python
class MessageBus:
    def __init__(self):
        self.inbound: asyncio.Queue[InboundMessage] = asyncio.Queue()
        self.outbound: asyncio.Queue[OutboundMessage] = asyncio.Queue()
```

The bus uses Python async queues (`asyncio.Queue`). This means the producer doesn't need to wait for the consumer — they are independent processes.

The bus **decouples** channels from the agent. Telegram knows nothing about the AgentLoop, and the AgentLoop knows nothing about Telegram. They only know the bus.

---

## 7. Message Processing

The `Orchestrator` (`openbotx/agent/orchestrator.py`) runs in the background, waiting for messages in the inbound queue:

```python
async def run(self):
    while not self._stop_event.is_set():
        try:
            msg = await asyncio.wait_for(self._bus.consume_inbound(), timeout=1.0)
            agent_name = await self._route(msg)
            agent = self._agents[agent_name]
            await agent.process_message(msg, agent_name=agent_name)
        except TimeoutError:
            continue  # check stop_event again
        except Exception as e:
            logger.error("orchestrator error: %s", e)  # single message failure doesn't crash
```

The 1-second timeout on `consume_inbound()` ensures the `_stop_event` is checked regularly, enabling graceful shutdown. Exceptions from individual message processing are caught and logged — a single bad message does not crash the orchestrator.

**Message routing:** When multiple agents are configured, the `AgentClassifier` uses an LLM call to determine the best agent. It analyzes the user's message plus the last 20 messages of conversation history and calls a `route(agent_name, confidence)` tool. The classifier uses hardcoded `max_tokens=256` and `temperature=0.0` for deterministic, fast classification. Assistant messages in the history are prefixed with `[Agent: name]` so the classifier can see which agent handled previous turns and maintain conversation continuity (it keeps the same agent unless the topic clearly changes). If the classifier returns an unknown agent name, it falls back to the default (first) agent. For single-agent setups, messages go directly to the default agent with no classification overhead.

When a message arrives, the selected `AgentLoop.process_message()` does the following in sequence:

```mermaid
graph TD
    A[Message arrives from Bus] --> B{Has task_id in metadata?}
    B -->|Yes| C[Retrieve existing Task]
    B -->|No| D[Create new Task]
    C --> E[Mark Task as DOING]
    D --> E
    E --> E1{Non-web channel?}
    E1 -->|Yes| E2["Broadcast chat:user_message"]
    E1 -->|No| F
    E2 --> F
    F{Is it a special command?}
    F -->|/new| G["Clear session, broadcast sessions:updated, respond"]
    F -->|/help| H[Return command list]
    F -->|No| I[Configure tool contexts]
    I --> I1{Has audio media?}
    I1 -->|Yes| I2["Transcribe audio, broadcast chat:transcription"]
    I1 -->|No| J
    I2 --> J
    J[Build System Prompt]
    J --> K[Retrieve session history]
    K --> L[Assemble messages]
    L --> M[Execute Agent Loop]
    M --> N[Save user + assistant to session]
    N --> N1["Broadcast sessions:updated"]
    N1 --> O[Publish response to Bus]
    O --> P[Mark Task as DONE]
    P --> Q{Need memory consolidation?}
    Q -->|Yes| R[Run consolidation]
    Q -->|No| S[End]
    R --> S
```

### 7.1. Task Creation/Recovery

Each user message becomes a **task**. The `process_message()` method accepts an optional `agent_name` parameter (set by the Orchestrator after classification). If provided, this overrides the agent loop's default name, and the task's `agent_name` is updated to match. If the message already has a `task_id` in its metadata (as with the REST API), it retrieves the existing task. Otherwise, it creates a new task with the title being the first 50 characters of the message. The task starts in the **DOING** state.

### 7.2. Special Commands

Before sending to the LLM, the agent checks if the message is a command:

- **`/new`** — Clears the session history and responds "Conversation cleared. How can I help you?"
- **`/help`** — Returns the list of available commands

If it's a command, the task is marked as **DONE** and the response is sent directly via the bus, without going through the LLM.

### 7.3. Tool Contexts

Before calling the LLM, the agent configures three tools with the current message context:

- **message tool**: receives `channel` and `chat_id` to know where to send intermediate messages. Also calls `start_turn()` which resets the `_sent_in_turn` flag — this tracks whether the tool has already sent a message in this turn
- **spawn tool**: receives `channel`, `chat_id`, and `parent_task_id` (to link subagents to the parent task)
- **cron tool**: receives `channel` and `chat_id` (so scheduled jobs know where they originated)

### 7.4. Error Handling

If the Agent Loop throws an exception, the error is caught and:
1. The task is marked as **ERROR** with the error message
2. An error response is sent to the user: `"I encountered an error: {error}"`

---

## 8. Context Building

The `ContextBuilder` (`openbotx/agent/context.py`) is responsible for assembling the "system prompt" — the text that tells the LLM who it is and what it knows. The prompt is built in this order:

```mermaid
graph TD
    A[Base identity] --> A1[Agent name]
    A1 --> B[Current date and time]
    B --> B1[Public URL]
    B1 --> B2[Project Structure - workspace and public paths]
    B2 --> C[AGENTS.md]
    C --> D[SOUL.md]
    D --> E[USER.md]
    E --> F[TOOLS.md]
    F --> G[Memory - MEMORY.md]
    G --> H[Always-on skills]
    H --> I[Available skills summary]
    I --> I1[Agent instructions]
    I1 --> J[Complete System Prompt]
```

### 8.1. Base Identity

```
"You are OpenBotX, a personal AI assistant."
```

If the agent has a name (multi-agent setup), this is followed by:

```
"You are acting as the **crypto** agent."
```

### 8.2. Current Date and Time

```
"Current date and time: 2025-01-15 14:30:00."
```

### 8.2a. Public URL and Project Structure

If a public URL is configured, it is included:

```
"Public URL: https://my-domain.com"
```

Then the directory context, which tells the agent about its workspace and the public directory:

```
# Project Structure
You have access to your workspace and the public directory. Always use absolute paths.

Workspace: /home/user/myproject/workspace
  Internal files: reports, data, drafts.

Public: /home/user/myproject/public
  Web-accessible at /public/ URL. Use for anything the user needs to access:
  - /home/user/myproject/public/media — images, audio, video (organized by date: YYYY/MM/DD)
  - /home/user/myproject/public/documents — PDFs, spreadsheets, exports
```

This explicitly provides the agent with the absolute paths for its workspace and the public directory, guiding it to use the correct directories for different file types.

### 8.3. Bootstrap Files (.md)

The system reads 4 files from the **project root** (not the workspace), in this fixed order:
1. `AGENTS.md`
2. `SOUL.md`
3. `USER.md`
4. `TOOLS.md`

Each is added as a section in the prompt (details in step 9).

### 8.4. Memory

If a `memory/MEMORY.md` file exists in the workspace, its content is added as a "Memory" section in the prompt.

### 8.5. Always-on Skills

Skills marked with `always: true` are automatically loaded and added to the prompt as individual sections.

### 8.6. Available Skills Summary

An XML list of all available skills is added, so the LLM knows what it can request. Each skill includes its name, description, file location (so the LLM can read it if needed), and availability status:

```xml
<available_skills>
  <skill><name>code-review</name><description>Review code for issues</description><location>/path/to/skills/code-review/SKILL.md</location><status>available</status></skill>
  <skill always="true"><name>git</name><description>Git operations</description><location>/path/to/skills/git/SKILL.md</location><status>available</status></skill>
</available_skills>
```

### 8.7. Agent Instructions

If the agent has an `instructions` field configured, it is appended as a dedicated section:

```
# Agent Instructions
You are a market analyst specializing in cryptocurrency. Always include disclaimers.
```

This is the last section in the system prompt, so it takes highest priority when instructions conflict with earlier context.

### 8.8. Final Message Assembly

After building the system prompt, `build_messages()` assembles the message list:

```python
[
    {"role": "system", "content": system_prompt},
    # ... session history (up to 500 messages) ...
    {"role": "user", "content": "current user message"}
]
```

If the message contains media (images), the agent loop resolves relative paths to base64 data URIs via the storage provider (see section 23). The user content is then assembled as multimodal:

```python
{"role": "user", "content": [
    {"type": "text", "text": "describe this image"},
    {"type": "image", "url": "data:image/jpeg;base64,/9j/4AAQ..."}
]}
```

Before sending to the LLM API, the provider converts this to the OpenAI-compatible format:

```python
{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,/9j/4AAQ..."}}
```

Using data URIs instead of HTTP URLs ensures compatibility with all cloud LLM providers, which cannot access `localhost` URLs.

---

## 9. The .md Files

These files reside at the project root (where `config.yml` lives) and define the agent's personality and behavior:

### SOUL.md — The Agent's "Soul"

Defines personality, tone of voice, and general behavior rules. Example:

```markdown
You are a helpful AI assistant.
- Always be polite and professional
- Respond in the same language as the user
- When unsure, ask for clarification
```

### USER.md — User Information

Contains information about the user that helps the agent personalize responses:

```markdown
- Name: Paulo
- Preferred language: Portuguese
- Timezone: America/Sao_Paulo
```

### AGENTS.md — Agent Descriptions

Describes the available agents and their capabilities:

```markdown
## Main Agent
General-purpose assistant capable of file operations, web search, and code execution.
```

### TOOLS.md — Tools Documentation

Provides additional instructions on how to use tools:

```markdown
## File Operations
When reading files, always check if the file exists first.
```

All these files are **optional**. If they don't exist, the agent works with the base identity. They are read **every time** a message is processed, so you can edit them at any moment and the effect is immediate.

---

## 10. Skills

Skills are extra capabilities you can give to the agent. Each skill is a Markdown file with specific instructions.

### How They Are Organized

Skills reside in two directories:
- **Built-in**: `openbotx/skills/` (shipped with the system)
- **Workspace**: `workspace/skills/` (created by the user)

Each skill is a folder with a `SKILL.md` file inside:

```
skills/
  code-review/
    SKILL.md
  git/
    SKILL.md
  summarize/
    SKILL.md
```

### SKILL.md Format

Each file has a **YAML frontmatter** at the top (between `---`) and the content below:

```markdown
---
name: code-review
description: Reviews code for bugs and improvements
always: false
requires:
  bins: []
  env: []
---

When asked to review code, analyze it for:
1. Bugs and logic errors
2. Security vulnerabilities
3. Performance issues
```

### Frontmatter Fields

| Field | Description |
|---|---|
| `name` | Skill name (used as identifier) |
| `description` | Short description (appears in the skills summary) |
| `always` | If `true`, the content is automatically included in every message's prompt |
| `requires.bins` | Programs that must be installed (e.g., `git`, `npm`). Checked via `shutil.which()` |
| `requires.env` | Environment variables that must exist (e.g., `BRAVE_API_KEY`). Checked via `os.environ.get()` |

The `bins` and `env` fields accept both a single string and a list.

### How They Are Loaded

The `SkillsLoader` (`openbotx/agent/skills.py`) does the following:

1. Scans skill directories (**built-in first**, then workspace)
2. Workspace skills with the same name **override** built-in ones
3. For each skill, reads the `SKILL.md` and parses the frontmatter using a regex `^---\n...\n---\n`
4. Checks if dependencies are satisfied (binaries installed, env vars present)
5. Tags each skill with a `source` field: `"builtin"` for skills from `openbotx/skills/`, `"project"` for skills from `workspace/skills/`. This is exposed via the REST API and displayed in the web UI as a visual tag on each skill card
6. Skills with `always: true` are included in the prompt automatically — **but only if their requirements are satisfied**. An `always: true` skill with unsatisfied requirements (missing binary or env var) is silently excluded from the prompt, preventing broken instructions from being injected
7. Skills with `always: false` appear in the available skills list for the LLM to use when needed
8. Skills with unsatisfied dependencies appear as `status="unavailable"` in the skills summary and are not loaded when requested

---

## 11. Creating New Skills

To create a new skill, follow these steps:

### Step 1: Create the Folder

```bash
mkdir -p workspace/skills/my-skill
```

### Step 2: Create the SKILL.md

```markdown
---
name: my-skill
description: Does something very useful
always: false
requires:
  bins: []
  env: []
---

Instructions for the agent on how to use this skill.

When the user asks to use "my-skill", do the following:
1. First step
2. Second step
3. Third step
```

### Step 3: Use It

The skill automatically appears in the available skills list. The agent can use it when the user asks for something related to its description.

### Always-on Skills

If you want the skill to always be active (without needing to be requested), set `always: true`:

```yaml
---
name: project-rules
description: Rules the agent must always follow
always: true
---

Rules:
- Always respond in Portuguese
- Never delete files without confirming
```

### Skills with Dependencies

If the skill requires an installed program or environment variable:

```yaml
---
name: docker-helper
description: Helps with Docker
requires:
  bins: [docker, docker-compose]
  env: [DOCKER_HOST]
---
```

If dependencies are not satisfied, the skill appears as "unavailable" and is not used.

---

## 12. Agent Loop

The Agent Loop (`_run_agent_loop()` in `openbotx/agent/loop.py`) is the heart of the processing. It implements the **ReAct** pattern (Reason + Act) — the LLM thinks, acts (uses tools), observes the result, and repeats.

```mermaid
graph TD
    A[Send messages + tool definitions to LLM] --> B{LLM responded with...}
    B -->|Plain text| C[Return as final response - END]
    B -->|Tool calls| D[For each tool call:]
    D --> E[ToolRegistry finds the tool]
    E --> F[Validate parameters]
    F --> G[Execute tool]
    G --> H["Add result to messages (role: tool)"]
    H --> I{More tool calls?}
    I -->|Yes| D
    I -->|No| J{Hit iteration limit?}
    J -->|No| A
    J -->|Yes| K[Return limit reached message]
```

### Real-time Broadcasting

During processing, the agent broadcasts events via the `EventDispatcher` so the frontend can show progress. All `chat:*` events include `agent_name` for multi-agent identification:

- **`chat:tool_use`** — when a tool is executed. Includes `tool` (human-readable name like `Read File`, `Web Search`) and `description` (human-readable summary of the tool call with arguments)
- **`chat:thinking`** — when the LLM returns reasoning content (see below)
- **`chat:user_message`** — when a non-web message arrives (e.g., from Telegram or cron). Includes `channel`, `content`, and `media`. This allows the web UI to display messages from other channels in real time
- **`chat:transcription`** — when audio media is transcribed. Includes the transcription text, which is also prepended to the user message content
- **`sessions:updated`** — after saving each conversation turn (user + assistant messages) to the session. Triggers sidebar reload in the frontend

### Extended Thinking (Reasoning)

Some LLM models support **extended thinking** — a feature where the model exposes its internal chain-of-thought alongside the final response. This is a model-specific capability, not something OpenBotX controls.

**Which models support it:**
- Anthropic Claude models with extended thinking enabled (e.g., `claude-sonnet-4-20250514` with thinking mode)
- Other providers may add support via LiteLLM as they release thinking-capable models

**How it flows through the system:**

1. The agent loop sends a request to the LLM via `provider.chat()`
2. LiteLLM returns the response with an optional `reasoning_content` field on the message object
3. `LiteLLMProvider` extracts it: `getattr(message, "reasoning_content", None)` and includes it in the `LLMResponse` dataclass
4. The agent loop checks if `reasoning_content` exists. If it does, it broadcasts a `chat:thinking` WebSocket event:

```python
if response.reasoning_content and self._dispatcher:
    await self._dispatcher.broadcast("chat:thinking", {
        "task_id": task_id,
        "chat_id": chat_id,
        "content": response.reasoning_content,
        "agent_name": agent_name,
    })
```

5. The frontend receives this event and can display the model's thought process (e.g., in a collapsible "thinking" section above the response)

**What happens with the reasoning content after broadcast:**
- It is saved into the conversation messages via `ContextBuilder.add_assistant_message()` (as the `reasoning_content` field)
- However, it is **stripped before sending to the LLM** on subsequent turns — `_sanitize_messages()` only keeps `role`, `content`, `tool_calls`, `tool_call_id`, and `name`. The reasoning is not re-sent to the model
- This means reasoning is broadcast once for real-time display, stored in the session for history, but never re-injected into future LLM calls

For models that don't support extended thinking, `reasoning_content` is simply `None` and no `chat:thinking` event is broadcast. The agent loop works identically in both cases.

### Iteration Limit

The loop has a maximum iteration limit (default: **40**, configurable via `params.max_iterations`). If the agent hits this limit without reaching a final response, it returns:

```
"I've reached my processing limit. Please try again or simplify your request."
```

### Output Limits

Each tool manages its own output limits internally. There is no global truncation applied by the agent loop or `ContextBuilder` — tool results are passed through as-is. This design ensures each tool controls the size and format of its results appropriately:

- **read_file** — 50 KB per read, with line-based pagination (offset/limit parameters)
- **exec** — 200 KB, tail-based truncation (keeps the last 200 KB, where errors and results typically appear)
- **http_client** — 50 KB response body truncation
- **web_fetch** — 50 KB content extraction limit

Other tools (file operations, web search, memory, etc.) return naturally small results and don't need truncation.

### Practical Example

Imagine the user asks "List the files in the docs/ folder":

**Iteration 1:**
- LLM receives the message and decides to call the `list_dir` tool with `{"path": "docs/"}`
- The tool returns: `"architecture.md\nconfiguration.md\napi.md\nskills.md\ntools.md"`
- Result is added to messages

**Iteration 2:**
- LLM receives the result and generates text: "The files in the docs/ folder are: architecture.md, configuration.md, ..."
- Since it's plain text (no tool calls), the loop ends
- This is the final response sent to the user

---

## 13. AI Provider Selection

OpenBotX supports multiple AI providers via **LiteLLM**. The selection of which provider to use follows a cascade logic in `Config.get_provider()` (`openbotx/config/schema.py`):

```mermaid
graph TD
    A["Configured model (e.g., anthropic/claude-sonnet-4-20250514)"] --> B{Has prefix with /?}
    B -->|Yes| C["Extract prefix (e.g., 'anthropic')"]
    C --> D{Prefix matches a configured provider with API key?}
    D -->|Yes| E[Use that provider]
    D -->|No| F[Continue to keyword search]
    B -->|No| F
    F --> G{Any provider has a keyword matching the model name?}
    G -->|Yes| H[Use that provider]
    G -->|No| I{Any provider configured with an API key?}
    I -->|Yes| J[Use the first one found]
    I -->|No| K[No provider available]
```

### Model Name Resolution

The `LiteLLMProvider` (`openbotx/providers/litellm_provider.py`) transforms the model name before sending to LiteLLM:

1. If there's a configured **gateway** (explicit provider), it applies the gateway prefix and optionally strips the original prefix
2. Otherwise, it looks up the provider specification by model name and adds the correct LiteLLM prefix

### Prompt Caching

Cloud LLM providers like Anthropic charge tokens to process the system prompt and tool definitions on every API call. Since these rarely change between turns (the system prompt, .md files, memory, and tool schemas are the same throughout a conversation), re-processing them on every call wastes time and money.

**Prompt caching** tells the provider to keep these blocks in a temporary server-side cache. On subsequent calls within the same session, the provider recognizes the cached content and skips re-processing, reducing both latency and cost.

Currently, two providers support this: **Anthropic** and **OpenRouter**. The flag `supports_prompt_caching` is set per provider in `openbotx/providers/registry.py`.

When enabled, `_apply_cache_control()` in `openbotx/providers/litellm_provider.py` transforms the messages before sending to the API:

**System message** — the content is converted from a string to a list of content blocks, with `cache_control` on the last block:

```python
# Before:
{"role": "system", "content": "You are OpenBotX..."}

# After:
{"role": "system", "content": [
    {"type": "text", "text": "You are OpenBotX...", "cache_control": {"type": "ephemeral"}}
]}
```

**Tool definitions** — `cache_control` is added to the last tool in the list:

```python
# Before:
[{"type": "function", "function": {"name": "read_file", ...}}, ...]

# After (last tool only):
[..., {"type": "function", "function": {"name": "generate_image", ...}, "cache_control": {"type": "ephemeral"}}]
```

The `ephemeral` type means the cache is temporary — the provider decides how long to keep it (typically 5 minutes of inactivity for Anthropic). Non-system messages (user, assistant, tool results) are **not** cached because they change every turn.

This transformation is applied automatically and transparently — the rest of the codebase works with regular strings and lists, unaware of caching.

### LLM Error Recovery

- **Malformed JSON**: When the LLM returns tool call arguments with invalid JSON, the system uses `json_repair.loads()` to attempt automatic correction
- **Empty content**: Messages with empty content are replaced with `"(empty)"` to avoid provider 400 errors
- **Sanitization**: Only allowed keys (`role`, `content`, `tool_calls`, `tool_call_id`, `name`) are sent to the LLM — extra fields are stripped

---

## 14. Tools

Tools are capabilities that the agent can use to interact with the world. Each tool is a Python class that inherits from `Tool` (`openbotx/tools/base.py`) and implements the `execute()` method.

### Tool Registry

The `ToolRegistry` (`openbotx/tools/registry.py`) manages all tools:

```python
class ToolRegistry:
    def register(self, tool: Tool)           # register a tool
    def get_definitions(self) -> list[dict]  # return schemas for the LLM
    async def execute(name, params) -> str   # execute a tool
```

When the AgentLoop calls the LLM, it sends tool definitions (name, description, parameters) so the LLM knows what's available.

### Available Tools

| Tool | Description |
|---|---|
| `read_file` | Read file contents |
| `write_file` | Write content to a file |
| `edit_file` | Edit parts of an existing file |
| `list_dir` | List files and folders in a directory |
| `exec` | Execute shell commands |
| `web_search` | Search the web (Brave Search API) |
| `web_fetch` | Fetch content from a URL |
| `http_client` | Make HTTP requests (GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS) with download/upload support |
| `rss_reader` | Read RSS/Atom feeds and return latest entries |
| `message` | Send intermediate messages to the user |
| `spawn` | Create subagents for parallel tasks |
| `cron` | Schedule recurring or one-time tasks |
| `memory_save` | Save information to long-term memory |
| `memory_read` | Read MEMORY.md or HISTORY.md on demand |
| `memory_search` | Search across memory files for specific information |
| `browser` | Browser automation (Chrome/Chromium via CDP) |
| `generate_image` | Generate images (if configured) |

### Parameter Validation

Before executing any tool, the `ToolRegistry` validates parameters using the JSON schema defined by the tool. Validation includes:
- Required field checking (`required`)
- Type validation (`string`, `integer`, `boolean`, `array`, `object`)
- Enum verification (allowed values)
- Minimum and maximum limits

### Tool Error Handling

When a tool fails, the result includes the error message followed by a hint for the LLM:

```
Error: File not found: config.yml

[Analyze the error above and try a different approach.]
```

This hint is automatically appended by the `ToolRegistry` to any result starting with "Error" or when an exception occurs. This instructs the LLM to try a different approach instead of repeating the same error.

If the tool is not found, the error message lists all available tools, helping the LLM self-correct.

### Workspace Restriction and PathResolver

By default, file tools (`read_file`, `write_file`, `edit_file`, `list_dir`), the HTTP client (`http_client`), and the shell (`exec`) are restricted to the agent's workspace and the shared public directory. The restriction is enforced by the `PathResolver` class (`openbotx/helpers/path.py`):

- **File tools and HTTP client**: All use a `PathResolver` instance for path resolution. The resolver:
  1. Expands `~` (home directory) via `Path.expanduser()`
  2. Resolves relative paths against the agent's workspace
  3. When `tools.general.restrict_to_workspace` is enabled, verifies the resolved path falls within one of the allowed directories (workspace or public). If not, raises a `PermissionError`
- **Per-agent isolation**: Each agent has its own `PathResolver` with `allowed_dirs = [agent_workspace, public_dir]`. In multi-agent setups, agents cannot access each other's workspaces
- **Shell (exec)**: The working directory is set to the agent's workspace. The `PathResolver.is_restricted` property is used to determine whether workspace restriction is active for the exec tool

### Shell Safety Guards (exec)

The `exec` tool (`openbotx/tools/shell.py`) has multiple layers of protection:

**Blocked commands** — Regex patterns that prevent execution:
- `rm -rf`, `del /f`, `rmdir /s` (destructive deletion)
- `format`, `mkfs`, `diskpart` (disk formatting)
- `dd if=`, `> /dev/sd` (direct device writing)
- `shutdown`, `reboot`, `poweroff` (machine shutdown)
- Fork bombs (`:(){ ... };:`)

**Path traversal protection** — Blocks commands containing `../` or `..\`

**Absolute path restriction** — When `restrict_to_workspace=True`, absolute paths in the command are verified to ensure they are within the working directory

**Timeout** — Commands exceeding the timeout (default: 60s) are automatically killed with `process.kill()`

**Truncation** — Output larger than **200 KB** (200,000 characters) is truncated using tail-based truncation: only the last 200 KB is kept, prefixed with `[Output truncated: showing last 200000 of N chars]`. This preserves the most recent output where errors and results typically appear

### Browser (CDP Automation)

The `browser` tool controls Google Chrome via **Chrome DevTools Protocol (CDP)** (visible by default, headless optional). It uses a multi-tab architecture that allows the main agent and subagents to use the browser concurrently, each in its own isolated tab.

**Architecture:**

```
┌─────────────────────────────────────────────┐
│          _ChromeInstance (singleton)         │
│   One Chrome process, shared across all      │
│   BrowserTool instances                      │
│                                              │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│   │  Tab #1  │ │  Tab #2  │ │  Tab #3  │   │
│   │  (main)  │ │ (sub #1) │ │ (sub #2) │   │
│   └──────────┘ └──────────┘ └──────────┘   │
└─────────────────────────────────────────────┘
```

- **Profile**: Uses `~/.openbotx/chrome-profile` as the profile directory (shared across all projects so the user doesn't need to reconfigure Chrome for each one)
- **Singleton Chrome process**: `_ChromeInstance` manages a single Chrome process. It starts lazily on the first `open_tab()` call and is shared by all `BrowserTool` instances
- **Per-instance tabs**: Each `BrowserTool` instance gets its own CDP target (tab) via `open_tab()`. The main agent and each subagent operate on independent tabs without interfering with each other
- **Available actions**: `navigate`, `snapshot` (page text, max 50,000 characters), `screenshot`, `click`, `type`, `evaluate` (JavaScript), `wait`
- **Auto-detection**: Searches for Chrome in standard locations on macOS, Linux, and Windows
- **Tab cleanup**: `close_tab()` closes a single tab. Subagents always call this in a `finally` block, ensuring tabs are released even when errors occur (see section 15)
- **Process cleanup**: On server shutdown, `cleanup()` closes the CDP connection and terminates the Chrome process entirely

---

## 15. Subagents

Subagents are independent agents that run in parallel to execute specific tasks. They are created by the main agent using the `spawn` tool.

### Fire-and-Forget Model

Spawning a subagent is **asynchronous** — the main agent does not wait for the result. The full lifecycle works as follows:

```mermaid
sequenceDiagram
    participant U as User
    participant AL as Agent Loop
    participant S as SubagentManager
    participant SUB as Subagent (background)
    participant BUS as Message Bus

    U->>AL: "Research topic X and Y"
    AL->>S: spawn(task="research topic X")
    S-->>AL: "Subagent spawned (task: abc123)"
    AL->>S: spawn(task="research topic Y")
    S-->>AL: "Subagent spawned (task: def456)"
    AL->>BUS: "I've started two research tasks."
    Note over AL: Main agent's task is DONE. Agent loop goes back to waiting.

    Note over SUB: Minutes later...
    SUB->>BUS: "[Subagent abc123 completed]: findings about X..."
    BUS->>AL: New InboundMessage (new task created)
    Note over AL: Session history contains the original conversation,<br/>so the LLM understands this is the result it requested.
    AL->>BUS: "Here's what I found about X: ..."
```

Step by step:

1. The LLM calls `spawn(task="...")` during its agent loop iteration
2. `SubagentManager.spawn()` creates an `asyncio.Task` in the background and returns **immediately** with `"Subagent spawned (task: abc123): ..."`
3. That string goes back to the LLM as a tool result. The LLM can spawn more subagents, use other tools, or finish its response
4. The main agent's task completes (DONE). The agent loop goes back to `bus.consume_inbound()`, waiting for the next message

When the subagent finishes (seconds or minutes later):

5. It publishes an `InboundMessage` to the bus: `"[Subagent abc123 completed]: result..."`
6. The agent loop picks this up as a **completely new message** and creates a new task for it
7. The system prompt and **full session history** are rebuilt — this includes the earlier conversation where the user asked the question and the agent decided to spawn
8. The LLM reads the history, sees its own spawn decision, and connects the subagent result to the original request. It then formulates a response using the result

The agent "remembers" because of the **session history** — not because of any explicit callback or state machine. The LLM reads the conversation flow and infers the relationship between the spawn and its completion.

### Subagent Restrictions

Subagents have **limited access** to tools:

| Allowed | Blocked |
|---|---|
| `read_file`, `write_file`, `edit_file`, `list_dir` | `message` (send messages to user) |
| `exec` (shell) | `spawn` (create other subagents) |
| `web_search`, `web_fetch` | `cron` (schedule tasks) |
| `http_client`, `rss_reader` | `memory_save`, `memory_read`, `memory_search` |
| `browser`, `generate_image` | |

This prevents subagents from multiplying uncontrollably, sending unexpected messages, or accessing memory. Subagents share the same `PathResolver` as the parent agent, so they have identical directory access restrictions.

**Browser tab isolation** — Each subagent creates its own browser tab via `BrowserTool`. The tab is always closed in a `finally` block when the subagent finishes (whether it succeeds, fails, or throws an exception). This guarantees tabs are never leaked, even under error conditions. See section 14 for the multi-tab architecture.

### Differences from Main Agent

| Feature | Main Agent | Subagent |
|---|---|---|
| Max iterations | 40 (configurable) | **15** (hardcoded) |
| Max tokens | Configurable (default 8192) | **4096** (hardcoded) |
| Temperature | Configurable (default 0.1) | **0.1** (hardcoded) |
| System prompt | Full (SOUL + USER + memory + skills + agent instructions) | **Simplified** ("You are a subagent..." with workspace + public paths) |
| Session history | Yes | **No** |
| Memory | Yes | **No** |
| Tools | All (17) | **11** (no message, spawn, cron, memory_save, memory_read, memory_search) |
| Tool result truncation | Per-tool (each tool manages its own output limits) | **500 chars** (inline truncation after tool execution) |
| Model | Configurable per agent | **Inherits from parent agent** |
| PathResolver | Per-agent (workspace + public) | **Shared** with parent agent |

The subagent's system prompt is intentionally minimal:

```
You are a subagent of OpenBotX. Complete the following task and report results. Be concise and efficient.
Workspace: /path/to/workspace (internal files)
Public: /path/to/public (web-accessible files)
Always use absolute paths.
```

### Completion

When the subagent completes its task:
1. The task is marked as **DONE** with the result (first 500 characters)
2. An `InboundMessage` is published to the bus with the format `[Subagent {task_id} completed]: {result}` (first 300 characters). The message metadata includes `system_message: true` and `subagent_task_id`, which the main agent loop uses to identify it as a subagent completion announcement rather than a regular user message
3. This message returns to the main agent, which can use the result to continue its work

If the subagent fails, the task is marked as **ERROR** with the error message.

### Background Task Tracking

The `SubagentManager` maintains a `set[asyncio.Task]` with all background tasks. When one finishes, it is automatically removed from the set via `add_done_callback`.

---

## 16. Memory and Consolidation

The memory system allows the agent to remember important information across conversations.

### Structure

Memory resides in the `memory/` folder of the workspace. The `MemoryStore` auto-creates this directory on initialization (`mkdir(parents=True, exist_ok=True)`), so it's always available even on a fresh workspace:

```
workspace/
  memory/
    MEMORY.md     # Long-term memory (facts, preferences)
    HISTORY.md    # Consolidated history (conversation summaries)
```

### How Memory Is Used

Memory is loaded **on every message**, not once at startup. The `ContextBuilder.build_system_prompt()` calls `memory.get_memory_context()` each time it assembles the system prompt. This method reads `memory/MEMORY.md` from disk, so any changes to the file (whether from consolidation, the `memory_save` tool, or manual editing) take effect immediately on the next message.

The content is injected as a `# Memory` section in the system prompt, after the bootstrap files (AGENTS.md, SOUL.md, USER.md, TOOLS.md) and before the skills:

```
[identity]
[date/time]
[AGENTS.md]
[SOUL.md]
[USER.md]
[TOOLS.md]

# Memory                    ← MEMORY.md content goes here
- User prefers Portuguese
- Timezone: America/Sao_Paulo
- ...

[always-on skills]
[available skills summary]
```

If `memory/MEMORY.md` does not exist or is empty, the section is omitted entirely — no placeholder is added. This means a fresh workspace with no memory produces a shorter system prompt with fewer tokens.

The two memory files serve different purposes:

| File | Purpose | How it changes |
|---|---|---|
| `MEMORY.md` | Active long-term memory — facts, preferences, context about the user. Included in every system prompt | **Overwritten** on each consolidation with an updated version. Can also be written directly by the `memory_save` tool during conversation |
| `HISTORY.md` | Chronological conversation summaries with timestamps. Not included in the prompt — serves as an audit log | **Appended** to on each consolidation. Grows over time |

Only `MEMORY.md` affects the agent's behavior. `HISTORY.md` is purely archival — it provides a timeline of past interactions but is never sent to the LLM.

### Automatic Consolidation

Consolidation happens **automatically** when the number of unconsolidated messages in the session exceeds `memory_window` (default: **100 messages**).

```mermaid
graph TD
    A[Response sent] --> B["Calculate: total - last_consolidated"]
    B --> C{"≥ memory_window (100)?"}
    C -->|No| D[Nothing to do]
    C -->|Yes| E[Extract unconsolidated messages]
    E --> F[Create temporary consolidation agent]
    F --> G[Send to LLM with consolidation instructions]
    G --> H["LLM calls memory_save(history_entry, updated_memory)"]
    H --> I["Append summary to HISTORY.md"]
    H --> J["Overwrite MEMORY.md with updated content"]
    I --> K["Update last_consolidated to current position"]
    J --> K
    K --> L[Save session]
```

The process in detail:

1. `_check_consolidation()` checks: `total_messages - last_consolidated >= memory_window`
2. If yes, extracts unconsolidated messages from the session. **Only user and assistant text messages are included** — tool calls (`role: "assistant"` with `tool_calls`) and tool results (`role: "tool"`) are filtered out. This keeps the consolidation input focused on the actual conversation content
3. Creates a temporary "consolidation agent" with access **only** to the `memory_save` tool
4. Sends the messages to the LLM with instructions:

```
"You are a memory consolidation agent. Analyze the conversation below and:
1. Write a timestamped summary for HISTORY.md
2. Update the long-term MEMORY.md with important facts, preferences,
   and context about the user.

Current MEMORY.md content:
{current content or '(empty)'}

Use the memory_save tool to persist both."
```

5. The LLM analyzes and calls `memory_save` (loop of up to **5 iterations** to ensure the LLM has a chance to complete)
6. `memory_save` writes:
   - `history_entry` → **appended** to the end of `HISTORY.md`
   - `updated_memory` → **overwrites** the entire `MEMORY.md`
7. The `last_consolidated` cursor is updated
8. If consolidation fails, the error is logged but **does not interrupt** the main flow

### memory_save Tool (Manual Use)

The agent can also call `memory_save` during a normal conversation if the user asks to remember something important. In this case, the information is saved directly to the memory files.

---

## 17. Sessions

A **session** represents a single continuous conversation between a user and the agent. It stores the full message history — user messages, assistant responses, tool calls, and tool results — so the LLM has context from previous turns. Without sessions, every message would be processed in isolation with no memory of what was said before.

The `SessionManager` (`openbotx/session/manager.py`) manages the entire lifecycle: creation, loading, saving, listing, and deletion.

### What a Session Contains

The `Session` dataclass holds:

| Field | Type | Description |
|---|---|---|
| `key` | `str` | Unique identifier (e.g., `web:direct`, `telegram:123456`) |
| `messages` | `list[dict]` | Full conversation history — each entry has `role`, `content`, `timestamp`, and optionally `tool_calls`, `tool_call_id`, `name` |
| `created_at` | `datetime` | When the session was first created |
| `updated_at` | `datetime` | Last modification timestamp |
| `metadata` | `dict` | Arbitrary metadata dictionary |
| `last_consolidated` | `int` | Cursor position for memory consolidation (see section 16) |
| `live_state` | `dict` | Transient runtime state (e.g., `tool_uses`, `agent_name`). Populated during agent execution and returned via the chat history API, but **never persisted** to JSONL. Cleared when the task completes. Allows the frontend to restore in-progress state on page refresh |

### Session Key

Each session is identified by a **key** derived from the incoming message. The default formula is:

```
session_key = "{channel}:{chat_id}"
```

Examples:
- **Web (default):** `web:a1b2c3d4-...` — when the frontend sends a message with a UUID `session_id`
- **Web (custom):** `web:project-alpha` — when the frontend sends `session_id="project-alpha"`
- **Telegram:** `telegram:123456789` — the Telegram chat ID
- **Cron:** `cron:cron-{job_id}-{hex}` — each cron job execution gets a unique session with `channel="cron"` and a generated `chat_id`
- **Heartbeat:** `heartbeat:heartbeat` — the heartbeat service uses `channel="heartbeat"` and `chat_id="heartbeat"`

This key determines which JSONL file is loaded and which conversation history the agent sees.

### session_key_override

The `InboundMessage` dataclass has a `session_key_override` field (default: `None`). When set, it **completely replaces** the default `channel:chat_id` key:

```python
@property
def session_key(self) -> str:
    return self.session_key_override or f"{self.channel}:{self.chat_id}"
```

This is an extension point for custom integrations. The built-in channels (web, Telegram, heartbeat) all use the default `{channel}:{chat_id}` key — for example, the Heartbeat Service uses `channel="heartbeat"` and `chat_id="heartbeat"`, resulting in key `heartbeat:heartbeat` (see section 20). The override enables scenarios such as:

- **Custom API consumers** that want explicit control over which session a message belongs to (e.g., sending `session_key_override="project:backend"` to group messages by project instead of by channel)
- **Shared sessions** — multiple different users or channels routing messages into the same session by specifying the same override key
- **Topic-based sessions** — a single user splitting conversations into different sessions based on subject rather than the default one-session-per-chat model
- **External orchestrators** that inject messages via the bus and need to target a specific existing session by its exact key

Example — an external system publishing a message directly to the bus:

```python
msg = InboundMessage(
    channel="api",
    sender_id="external-system",
    chat_id="irrelevant",
    content="Generate the weekly report",
    session_key_override="reports:weekly",
)
await bus.publish_inbound(msg)
```

In this case, the session key will be `reports:weekly` regardless of the `channel` and `chat_id` values.

### Session Lifecycle

```mermaid
graph TD
    A[Message arrives] --> B["Compute session_key"]
    B --> C["SessionManager.get_or_create(key)"]
    C --> D{In cache?}
    D -->|Yes| E[Return cached session]
    D -->|No| F{JSONL file exists?}
    F -->|Yes| G[Load from file]
    F -->|No| H[Create empty session]
    G --> I[Cache and return]
    H --> I
    E --> J[Agent loop processes message]
    I --> J
    J --> K[Add user + assistant messages]
    K --> L["SessionManager.save(session)"]
    L --> M[Write JSONL + update cache]
    M --> N["Check consolidation (section 16)"]
```

Step by step:

1. **Key computation** — `InboundMessage.session_key` returns `session_key_override` if set, otherwise `{channel}:{chat_id}`
2. **Load or create** — `get_or_create(key)` checks the in-memory cache first; if not found, attempts to load from the JSONL file; if the file doesn't exist, creates a new empty `Session`
3. **Agent loop** — The agent uses `session.get_history()` to build the conversation context for the LLM
4. **Save** — After the agent loop completes, the user message and assistant response are appended to the session, and it's written back to disk
5. **Consolidation check** — If unconsolidated messages exceed `memory_window`, memory consolidation triggers (see section 16)

### Storage Format

Sessions are persisted as **JSONL** (JSON Lines) files in the `sessions/` folder of the workspace:

```
workspace/
  sessions/
    web_a1b2c3d4-e5f6-....jsonl
    telegram_123456789.jsonl
    heartbeat_heartbeat.jsonl
    reports_weekly.jsonl
```

The filename is derived from the session key: `:` is replaced with `_` and invalid filesystem characters are removed via `re.sub(r"[^\w\-.]", "_", key)`.

Each file has a **metadata line** as the first entry, followed by one line per message:

```jsonl
{"_type": "metadata", "key": "web:direct", "created_at": "2025-01-15T10:00:00", "updated_at": "2025-01-15T14:30:05", "metadata": {}, "last_consolidated": 0}
{"role": "user", "content": "Hello", "timestamp": "2025-01-15T14:30:00"}
{"role": "assistant", "content": "Hello! How can I help?", "timestamp": "2025-01-15T14:30:05"}
{"role": "user", "content": "Read the README file", "timestamp": "2025-01-15T14:31:00"}
{"role": "assistant", "content": "", "tool_calls": [{"id": "tc_1", "type": "function", "function": {"name": "read_file", "arguments": "{\"path\": \"README.md\"}"}}], "timestamp": "2025-01-15T14:31:02"}
{"role": "tool", "tool_call_id": "tc_1", "name": "read_file", "content": "# My Project\n...", "timestamp": "2025-01-15T14:31:03"}
{"role": "assistant", "content": "The README contains...", "timestamp": "2025-01-15T14:31:05"}
```

On save, the entire file is **rewritten** — metadata line first, then all messages sequentially. This ensures file consistency.

### In-Memory Cache

The `SessionManager` maintains an in-memory cache (`dict[str, Session]`):

1. `get_or_create(key)` checks the cache first — O(1) lookup
2. If not cached, loads from the JSONL file on disk
3. If the file doesn't exist, creates a new empty session
4. After every `save()`, the cache is updated with the latest state
5. `delete()` removes both the file and the cache entry

This means that during normal operation, sessions are only loaded from disk **once** — all subsequent access is from memory.

### History Retrieval

The `get_history(max_messages=500)` method returns the last **500 messages** from the session in the format the LLM API expects. This caps context size to avoid exceeding token limits. For each message, the following fields are included:

- `role` — `"user"`, `"assistant"`, or `"tool"`
- `content` — The message text
- `tool_calls` — Present on assistant messages that invoke tools
- `tool_call_id` — Present on tool result messages
- `name` — Tool name on tool result messages

### Clearing

The `/new` command (available via web chat or Telegram) clears the session:
- Removes **all messages** from the list
- Resets `last_consolidated` to **0**
- Saves the empty session to disk

This gives the user a fresh conversation while preserving long-term memory (which lives in `MEMORY.md`, not in the session).

### REST API Operations

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/chat/sessions` | List all sessions (any channel), sorted by last update (newest first) |
| `GET` | `/api/chat/sessions/{id}` | Return the complete history for a session |
| `DELETE` | `/api/chat/sessions/{id}` | Delete a session (file + cache) |

The `{id}` parameter uses key resolution (`_resolve_session_key`):

1. If the ID contains `:`, it is used as the session key directly (e.g., `web:abc123`, `heartbeat:heartbeat`)
2. Otherwise, the ID is prefixed with `web:` (standard user sessions)

This means the API works universally for any session type — web, heartbeat, telegram, or custom — as long as the user is authenticated.

---

## 18. Task Management

The task system works as a **Kanban board** that shows what the agent is doing in real time.

### Task States

| State | Meaning |
|---|---|
| **TODO** | Task created, awaiting start |
| **DOING** | Task in progress |
| **DONE** | Task completed successfully |
| **ERROR** | Task failed with an error |

### Flow

```mermaid
stateDiagram-v2
    [*] --> TODO: Task created
    TODO --> DOING: Agent starts processing
    DOING --> DONE: Processing complete
    DOING --> ERROR: Error during processing
    DOING --> TODO: Server restart (recovered)
    DOING --> ERROR: Server restart (subagent)
```

1. When the user sends a message, a task is created (state **TODO**)
2. Immediately changes to **DOING** when the agent starts processing
3. Upon completion, changes to **DONE** (with the first 200 characters of the result) or **ERROR** (with error message)

### Task Data Model

Each task stores the following fields:

| Field | Description |
|---|---|
| `id` | First 8 characters of a UUID4 (e.g., `"a1b2c3d4"`) |
| `title` | Short title (first 50-80 chars of the message) |
| `description` | Full message content |
| `state` | Current state: `TODO`, `DOING`, `DONE`, or `ERROR` |
| `agent_type` | `"agent"` (main) or `"subagent"` |
| `channel` | Origin channel (`"web"`, `"telegram"`) — used for recovery routing |
| `chat_id` | Origin chat/session ID — used for recovery routing |
| `parent_task_id` | ID of the parent task (for subagents) |
| `subagent_ids` | List of child subagent task IDs |
| `result` | First 200 characters of the result (on DONE) |
| `error` | Error message (on ERROR) |
| `created_at` | ISO 8601 timestamp |
| `updated_at` | ISO 8601 timestamp |
| `live_state` | Transient runtime state (e.g., `tool_uses` list). Populated during agent execution and included in API responses when non-empty, but **never persisted** to JSONL. Cleared when the task completes. Allows the frontend to restore active tool status on page refresh |

The `channel` and `chat_id` fields are set when the task is created and record which conversation originated it. This is essential for task recovery on restart — without them, the system wouldn't know where to route the re-queued message (see below).

### Parent-Child Hierarchy

When a subagent is created via `spawn`, it gets its own task with:
- `agent_type: "subagent"` (instead of `"agent"`)
- `parent_task_id`: pointing to the main agent's task

The parent task maintains a `subagent_ids` list with the IDs of all created subtasks. This allows visualizing the hierarchy in the Kanban board.

### Persistence

Tasks are saved in `tasks.jsonl` in the workspace. Each task is a JSON line, rewritten on every update.

### Task Recovery on Restart

If the server stops while tasks are in the DOING state (e.g., crash, Ctrl+C during processing), those tasks would be stuck forever — the task system is **reactive** and only executes when an `InboundMessage` arrives on the MessageBus.

On startup, `TaskManager._load()` detects and recovers interrupted tasks:

1. **Main tasks** (`agent_type="agent"`) are reset to **TODO** and added to a recovery list
2. **Subagent tasks** are set to **ERROR** with the message "interrupted by server shutdown" — they cannot run independently because they lack parent context, session history, and the simplified prompt needed to continue

After all services are started, the server lifespan re-queues recovered main tasks by publishing an `InboundMessage` for each one:

```python
for task in task_manager.get_recovered_tasks():
    msg = InboundMessage(
        channel=task.channel or "web",
        sender_id="system",
        chat_id=task.chat_id or "direct",
        content=task.description,
        metadata={"task_id": task.id, "recovered": True},
    )
    await bus.publish_inbound(msg)
```

The `channel` and `chat_id` stored on the task ensure the message is routed to the correct session. The `task_id` in metadata links it to the existing task, so the agent loop retrieves it (instead of creating a new one) and resumes processing.

### Real-time Broadcasting

Every state change is broadcast via WebSocket:
- **`task:created`** — when a task is created (payload: complete task as JSON)
- **`task:updated`** — when the state changes (payload: updated task as JSON)

The frontend receives these events and updates the Kanban board instantly.

---

## 19. WebSocket

WebSocket is the primary real-time communication channel between the browser and the server.

### WebSocketManager

The `WebSocketManager` (`openbotx/server/websocket.py`) maintains a set of active connections:

```python
class WebSocketManager:
    def __init__(self):
        self._connections: set[WebSocket] = set()
```

### Broadcast Events

| Event | Payload | When Sent |
|---|---|---|
| `chat:thinking` | `{ task_id, chat_id, content, agent_name }` | During the Agent Loop, if the LLM sends reasoning |
| `chat:tool_use` | `{ task_id, chat_id, tool, description, agent_name }` | When a tool is executed |
| `chat:message` | `{ content, chat_id, task_id, agent_name }` | When the agent finalizes a response |
| `chat:user_message` | `{ chat_id, content, media, channel }` | When a non-web user message is received (e.g., Telegram, cron). Allows the web UI to display messages from other channels in real time |
| `chat:transcription` | `{ chat_id, content }` | When audio media is transcribed (the transcription text is prepended to the user message) |
| `sessions:updated` | `{}` | After a session is saved or cleared (triggers sidebar reload) |
| `task:created` | Task object | When a task is created |
| `task:updated` | Task object | When a task's state changes |
| `channel:status` | `{ name, running }` | When a channel connects or disconnects |

### Session-Aware Message Filtering

All `chat:*` events include a `chat_id` field identifying which session the message belongs to. The frontend uses this to **filter messages by session** — only messages matching `currentSessionId` are displayed. This prevents messages from different sessions (e.g., heartbeat responses) from appearing in the wrong conversation.

```javascript
// Frontend filtering (chat store)
function _isCurrentSession(data) {
  return !data.chat_id || data.chat_id === currentSessionId.value
}
```

Messages from sessions other than the active one are silently ignored. The user can switch to another session to see its messages.

### Automatic Dead Connection Cleanup

When the server tries to send a message and fails (broken connection), the connection is automatically removed:

```python
async def broadcast(self, event_type, data):
    dead: set[WebSocket] = set()
    for ws in self._connections:
        try:
            await ws.send_text(msg)
        except Exception:
            dead.add(ws)
    self._connections -= dead  # remove dead connections
```

### Connection Keep-Alive

The frontend periodically sends "pings" over the WebSocket to ensure the connection is not closed due to inactivity. This is important because:

1. Proxies and load balancers may close idle connections
2. The browser may drop the connection if there's no activity
3. The server needs to detect disconnected clients

---

## 20. Heartbeat Service

The Heartbeat Service (`openbotx/heartbeat/service.py`) is a background process that periodically checks a file called `HEARTBEAT.md` in the workspace for tasks. If the file has actionable content, the service wakes the agent to process it.

### Who Writes HEARTBEAT.md?

**The user** (or an external system) — manually. Unlike cron jobs, which the agent creates programmatically via the `cron` tool, `HEARTBEAT.md` is a file the user edits directly in the workspace. Think of it as a **to-do list on the user's desk** that the agent checks periodically.

Typical use cases:
- Ongoing maintenance tasks ("check if backups are running")
- Monitoring instructions ("summarize today's error logs")
- Recurring checklists that change frequently and are easier to manage as a file than as cron jobs

The user adds or removes items by editing the file. The agent reads it but does not modify it — the user is responsible for updating `HEARTBEAT.md` as needed.

### How It Works

```mermaid
graph TD
    A["HeartbeatService._run_loop()"] --> B["Sleep for interval seconds (default: 1800)"]
    B --> C["Read workspace/HEARTBEAT.md"]
    C --> D{File has actionable content?}
    D -->|No| B
    D -->|Yes| E["Publish InboundMessage to bus"]
    E --> F["Agent reads HEARTBEAT.md and follows instructions"]
    F --> G["Agent responds with results or HEARTBEAT_OK"]
    G --> B
```

1. Every `interval` seconds (default: 1800 = 30 minutes), the service reads `HEARTBEAT.md`
2. The file is considered **empty** (no action) if it only contains blank lines, headers (`#`), or HTML comments (`<!--`)
3. If there is actionable content, the service publishes an `InboundMessage` with:
   - `channel="heartbeat"` — identifies the source as the heartbeat service
   - `chat_id="heartbeat"` — results in session key `heartbeat:heartbeat`, separate from user conversations
   - Since `heartbeat` has no dedicated channel handler, responses are routed to the WebSocket (the default fallback) so the user can see them in the browser
4. The agent receives the message, reads `HEARTBEAT.md`, and follows the instructions listed there
5. If nothing needs attention, the agent responds with `HEARTBEAT_OK`

The user can view heartbeat results by switching to the "Heartbeat" session in the web interface session list (see section 17).

### HEARTBEAT.md Format

The file is plain Markdown. Any line that is not a header, blank, or HTML comment is considered actionable:

```markdown
# Heartbeat Tasks

- Check if the backup ran successfully
- Summarize today's error logs
- Verify that the API health endpoint returns 200
```

### Heartbeat vs Cron

| Aspect | Heartbeat | Cron |
|---|---|---|
| **Trigger** | Periodic file check (every N seconds) | Scheduled (cron expression, interval, or specific time) |
| **Task definition** | Written by the user in `HEARTBEAT.md` | Created by the agent via the `cron` tool |
| **Management** | User edits a file manually | Agent adds/removes/lists jobs programmatically |
| **Session** | Dedicated (`heartbeat:heartbeat`) | Inherits from the conversation that created the job |
| **Persistence** | Markdown file in workspace | `cron_jobs.json` in workspace |
| **Use case** | Ongoing checklist the user maintains | Agent-scheduled automations |

### Configuration

```yaml
heartbeat:
  enabled: true    # default — set to false to disable
  interval: 1800   # seconds between checks (default: 30 minutes)
```

When `enabled` is `false`, the service logs "heartbeat disabled" on startup and does not start the background loop.

---

## 21. Scheduler (Cron)

The scheduler (`openbotx/cron/service.py`) allows programming tasks to be executed in the future or on a recurring basis.

### How It Works

The CronService runs in the background with a **tick every 5 seconds**. On each tick, it checks if any job needs to be executed:

```python
TICK_INTERVAL = 5.0  # seconds

async def run(self):
    while not self._stop_event.is_set():
        await asyncio.sleep(TICK_INTERVAL)
        await self._tick()
```

### Schedule Types

| Type | Description | Example | Next Run Calculation |
|---|---|---|---|
| `every` | Fixed interval | Every 3600s (1 hour) | `now + every_ms` |
| `cron` | Cron expression | `0 9 * * *` (daily at 9am) | Via `croniter` (supports timezone) |
| `at` | Specific date/time | `2025-01-20T10:00:00` | Fixed timestamp (one-time) |

### What Happens When a Job Executes

```mermaid
sequenceDiagram
    participant CS as CronService (tick every 5s)
    participant BUS as Message Bus
    participant AL as Agent Loop

    CS->>CS: Check: now >= next_run_ms?
    CS->>BUS: Publish InboundMessage(channel, sender="cron", content=message)
    Note over BUS: Metadata includes cron_job_id and cron_job_name
    BUS->>AL: AgentLoop consumes the message
    AL->>AL: Process normally (LLM + tools)
    CS->>CS: Update next_run_ms for next cycle
```

The cron message enters the bus like any other message — the AgentLoop doesn't know (and doesn't need to know) it came from a scheduled job.

### One-time Jobs

Jobs of type `at` have the flag `delete_after_run=True`. After execution, they are automatically removed from the job list.

### Persistence

Jobs are saved in `cron_jobs.json` in the workspace (indented JSON format). They survive server restarts.

### Job Creation

Jobs can be created in two ways:

1. **By the agent**: Using the `cron` tool (the LLM decides to create a schedule). Supports `add`, `list`, and `remove` actions. When adding, the channel and chat_id from the current conversation are automatically associated with the job
2. **Via REST API**: `POST /api/scheduler/jobs` with a JSON body containing `name`, `message`, and one of the scheduling fields (`cron_expr`, `every_seconds`, or `at`)

### Origin Tracking and Response Routing

Each cron job stores the **channel** and **chat_id** of the conversation where it was created. This determines where the agent's response will appear when the job fires.

```mermaid
sequenceDiagram
    participant U as User (Web Chat)
    participant AL as Agent Loop
    participant CRON as CronService
    participant BUS as Message Bus

    Note over U,AL: User creates the job from web chat
    U->>AL: "Remind me every hour to drink water"
    AL->>CRON: add_job(message="Drink water!")

    Note over CRON: 1 hour later...
    CRON->>BUS: InboundMessage(channel="cron", chat_id="cron-abc-f1e2d3")
    BUS->>AL: Agent loop processes the message
    Note over AL: Fresh session "cron:cron-abc-f1e2d3"
    AL->>BUS: OutboundMessage(channel="cron", content="...")
    BUS->>U: WebSocket broadcast (no dedicated cron channel handler)
```

The key detail: when the job fires, `ServerFactory.create_cron_callback()` generates a **unique session per execution** by constructing a `chat_id` from the job ID and a random hex suffix:

```python
chat_id = f"cron-{job.id}-{uuid4().hex[:6]}"
InboundMessage(
    channel="cron",
    sender_id="cron",
    chat_id=chat_id,
    content=job.payload.message,
    metadata={"cron_job_id": job.id, "cron_job_name": job.name},
)
```

Each execution creates a fresh session (e.g., `cron:cron-abc123-f1e2d3`), so recurring jobs don't accumulate context from previous runs. The cron job metadata (`cron_job_id`, `cron_job_name`) is passed through so the agent can identify which job triggered the execution.

Since `channel="cron"` has no dedicated channel handler, responses are routed to the WebSocket (the default fallback), where the user can view them by switching to the corresponding session in the web interface.

---

## 22. Output Routing

The `ChannelManager` (`openbotx/channels/manager.py`) is responsible for taking the agent's responses and delivering them to the correct recipient.

### How It Works

The ChannelManager runs a background task that consumes the bus outbound queue:

```python
async def _dispatch_outbound(self):
    while True:
        msg = await self.bus.consume_outbound()
        await self._route_message(msg)
```

### Message Filters

Before routing, two filters are applied:

| Metadata | Setting | Default | Effect |
|---|---|---|---|
| `progress: true` | `channels.send_progress` | `true` | Progress (intermediate) messages |
| `tool_hint: true` | `channels.send_tool_hints` | `false` | Hints about tools in use |

If the filter is disabled, the message is silently discarded.

### Routing

```mermaid
graph TD
    A[OutboundMessage arrives] --> B{Progress / tool_hint filters}
    B -->|Blocked| C[Discarded]
    B -->|Allowed| D{msg.channel?}
    D -->|web| E["ws_manager.broadcast('chat:message', ...)"]
    E --> F[Frontend receives via WebSocket]
    D -->|telegram| G[TelegramChannel.send]
    G --> H{Media type?}
    H -->|Text| I[Convert Markdown to Telegram HTML]
    I --> J{Message > 4000 chars?}
    J -->|Yes| K[Split into parts respecting word boundaries]
    J -->|No| L[Send via Telegram API]
    K --> L
    H -->|File| M[Send as document/photo via Telegram API]
```

### Telegram: Sending Details

The `TelegramChannel` has special handling for Telegram:

- **Markdown → HTML conversion**: Telegram uses an HTML subset. The system converts `**bold**`, `` `code` ``, code blocks, etc., to the equivalent Telegram HTML tags
- **Long message splitting**: Messages larger than **4,000 characters** are split into multiple parts, respecting word boundaries to avoid cutting mid-sentence
- **Typing indicator**: During processing, the bot sends "typing..." every **4 seconds** so the user knows it's working
- **Format fallback**: If HTML sending fails, retries as plain text

---

## 23. Media Pipeline

Media files (images, audio, documents) are stored with **relative paths only**. Each consumer resolves the file in the format it needs: base64 data URI for the LLM, raw bytes for Telegram, HTTP URL for the web interface. Audio files are transcribed to text via faster-whisper before being sent to the LLM.

### Design Principle

The system never stores absolute URLs or encoded data in the message. Instead, it stores a **relative path** (e.g., `public/media/2026/02/26/abc123.jpg`) and resolves on demand via the storage provider. This ensures compatibility across all consumers — cloud LLMs can't access `localhost` URLs, but they can process base64 data URIs.

**Date-based organization:** All media files are saved in date-organized subdirectories under `public/media/` using the `media_path()` helper from `openbotx/helpers/path.py`. The path format is `public/media/YYYY/MM/DD/{filename}`. This prevents directory bloat by distributing files across daily folders. Both `ImageGenerationTool` and `TelegramChannel` use this helper. `LocalStorage.write()` creates intermediate directories automatically.

### The `public/` Folder

All publicly-accessible files live under the `public/` directory at the project root:

```
project/
  public/
    media/
      abc123.jpg
      photo_xyz.png
    ...
  config.yml
  .env
```

The web server exposes `GET /public/{path}` to serve any file under this directory. This route works regardless of any configuration — the server always binds to the local `host:port` and serves files directly.

The `public_url` config field (`server.public_url` in `config.yml`) is **only** used when the system needs to generate absolute URLs for external access (e.g., `storage.get_url()` for sharing links). When empty (default), it falls back to `http://localhost:{port}`. On a VPS or production deployment, set it to the public domain (e.g., `https://my-domain.com`) so generated URLs point to the correct address.

### Storage Providers

The `StorageProvider` interface (`openbotx/storage/base.py`) defines the contract:

```python
class StorageProvider(ABC):
    async def read(path) -> bytes            # Raw bytes
    async def write(path, data) -> None
    async def delete(path) -> None
    async def list(prefix) -> list[str]
    async def exists(path) -> bool
    def get_url(path) -> str                 # Public HTTP URL
    def get_data_uri(path) -> str            # data:mime;base64,... for LLMs
```

Two implementations:

| Provider | Config `storage.type` | `get_url()` | `get_data_uri()` |
|---|---|---|---|
| `LocalStorage` | `"local"` (default) | `{public_url}/{path}` | Read file, detect MIME, encode base64 |
| `S3Storage` | `"s3"` | `https://{bucket}.s3.{region}.amazonaws.com/{path}` | Download from S3, encode base64 |

For `LocalStorage`, the `base_path` points to the **project root** directory. All paths are relative within it (e.g., `public/media/2026/02/26/abc123.jpg` resolves to `project/public/media/2026/02/26/abc123.jpg`). This allows the storage to handle any project file, not just public assets.

### Data Flow

```mermaid
graph TD
    A["Channel receives media"] --> B["Save to project/public/media/YYYY/MM/DD/abc123.jpg"]
    B --> C["InboundMessage.media = ['public/media/YYYY/MM/DD/abc123.jpg']"]
    C --> D["Agent Loop receives message"]
    D --> E{File type?}
    E -->|Image| F["storage.get_data_uri('public/media/YYYY/MM/DD/abc123.jpg')"]
    F --> G["data:image/jpeg;base64,/9j/4AAQ..."]
    G --> H["ContextBuilder: {type: image, url: data:...}"]
    H --> I["LLM Provider converts to OpenAI format"]
    I --> J["LLM processes the image"]
    E -->|Audio| K["storage.read('public/media/YYYY/MM/DD/voice.webm')"]
    K --> L["faster-whisper transcribes audio to text"]
    L --> M["Transcript prepended to message content"]
    M --> N["LLM processes the text"]
```

### Audio Transcription

Audio files (`.mp3`, `.wav`, `.ogg`, `.m4a`, `.webm`, `.aac`, `.flac`) are transcribed to text using **faster-whisper** (`openbotx/helpers/transcription.py`). The Whisper model (`base`, CPU, int8) is lazy-loaded on first use. The transcript is prepended to the message content as `[Audio transcription]: ...`, so the LLM receives it as text rather than binary data.

This applies to audio from any source — web uploads, Telegram voice messages, or any other channel that attaches audio files.

Each consumer resolves the path differently:

| Consumer | Method | Result |
|---|---|---|
| **LLM (Agent Loop)** | `storage.get_data_uri(path)` | `data:image/jpeg;base64,...` — works with all cloud providers |
| **Telegram outbound** | `storage.read(path)` | Raw bytes sent via Telegram API |
| **Web interface** | `GET /public/{path}` | HTTP file response served by FastAPI |
| **Public URL generation** | `storage.get_url(path)` | Absolute URL for sharing or embedding |

### Internal vs API Format

OpenBotX uses a clean internal format for image content blocks:

```json
{"type": "image", "url": "data:image/jpeg;base64,/9j/4AAQ..."}
```

Before sending to the LLM API, the provider automatically converts it to the OpenAI-compatible format:

```json
{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,/9j/4AAQ..."}}
```

This conversion happens transparently in `LLMProvider._convert_image_blocks()`, keeping the internal API clean while maintaining compatibility with all LLM providers via LiteLLM.

### Configuration

In `config.yml`:

```yaml
server:
  host: 0.0.0.0
  port: 8000
  public_url: ""  # optional — only for generating public URLs and opening browser

storage:
  type: local  # or "s3"
  # S3-specific fields:
  s3_bucket: my-bucket
  s3_region: us-east-1
  s3_access_key: ${AWS_ACCESS_KEY}
  s3_secret_key: ${AWS_SECRET_KEY}
```

### `public_url` Behavior

The web server always binds to `host:port` and serves everything locally — the `public_url` field does **not** change how the server runs. It is used in two places:

1. **`storage.get_url(path)`** — generates absolute URLs for external access (e.g., `https://my-domain.com/public/media/abc123.jpg`). When empty, uses `http://localhost:{port}`
2. **Browser auto-open** — when `openbotx start` runs, if `public_url` is set, the browser opens at that URL instead of `localhost`

Typical scenarios:

| Environment | `public_url` | Browser opens at | `get_url()` returns |
|---|---|---|---|
| Local development | `""` (empty) | `http://localhost:8000/app/` | `http://localhost:8000/public/media/...` |
| VPS with domain | `"https://bot.example.com"` | `https://bot.example.com/app/` | `https://bot.example.com/public/media/...` |
| VPS with IP | `"http://203.0.113.10:8000"` | `http://203.0.113.10:8000/app/` | `http://203.0.113.10:8000/public/media/...` |

---

## 24. Server Shutdown

When the server is stopped (Ctrl+C or shutdown signal), the lifespan executes the shutdown sequence:

```mermaid
graph TD
    A[Shutdown signal] --> B[HeartbeatService.stop]
    B --> C[Orchestrator.stop]
    C --> C1["For each agent: AgentLoop.stop"]
    C1 --> D[Browser cleanup - close Chrome if open]
    D --> E[Cancel orchestrator_task]
    E --> F[CronService.stop - set stop_event]
    F --> G[Cancel cron_task]
    G --> H[ChannelManager.stop]
    H --> I[Cancel outbound dispatch]
    I --> J["Stop channels (10s timeout each)"]
    J --> K[Shutdown complete]
```

**HeartbeatService.stop()** cancels the background loop and is the first service to stop — it prevents new heartbeat messages from being queued during shutdown.

**Orchestrator.stop()** sets its `_stop_event` and then calls `stop()` on every `AgentLoop` instance. Each `AgentLoop.stop()` calls `browser_tool.cleanup()` if the browser tool is registered, terminating the Chrome process and closing all tabs. Individual subagent tabs are already cleaned up via `close_tab()` in their `finally` blocks (see section 15).

**ChannelManager.stop()** stops each channel with a **10-second timeout** (`asyncio.wait_for`). This prevents the shutdown from hanging indefinitely if a channel (e.g., Telegram long-polling) takes too long to close. If a channel exceeds the timeout, the error is logged and shutdown continues with the remaining channels.

**Task state on shutdown:** Tasks that are in the DOING state when the server stops remain persisted as DOING in `tasks.jsonl`. On the next startup, they are recovered and re-queued automatically (see section 18 — Task Recovery on Restart).

---

## 25. Complete Cycle

Summary of the complete message flow, from start to finish:

```mermaid
sequenceDiagram
    participant U as User (Browser)
    participant WS as WebSocket
    participant BUS as Message Bus
    participant AL as Agent Loop
    participant LLM as AI Model
    participant T as Tool (write_file)
    participant TM as Task Manager
    participant CM as Channel Manager

    U->>WS: chat:send "Create a file hello.py"
    WS->>BUS: InboundMessage(channel="web")

    BUS->>AL: Consume message
    AL->>TM: Create Task "Create a file hello.py"
    TM-->>U: WebSocket: task:created
    AL->>TM: Task → DOING
    TM-->>U: WebSocket: task:updated

    AL->>AL: Build system prompt (SOUL + USER + memory + skills)
    AL->>AL: Retrieve session history
    AL->>LLM: Messages + tool definitions

    LLM-->>AL: tool_call: write_file(path="hello.py", content="print('Hello!')")
    AL-->>U: WebSocket: chat:tool_use {tool: "Write File"}
    AL->>T: Execute write_file
    T-->>AL: "File written: hello.py"

    AL->>LLM: Messages + tool result
    LLM-->>AL: "I created hello.py with a simple print statement."

    AL->>AL: Save to session (user + assistant)
    AL->>BUS: OutboundMessage(channel="web", content="I created hello.py...")

    BUS->>CM: Consume message
    CM-->>U: WebSocket: chat:message "I created hello.py..."

    AL->>TM: Task → DONE
    TM-->>U: WebSocket: task:updated

    AL->>AL: Check memory consolidation (if needed)
```

This cycle happens for **every message**, whether from web, Telegram, or cron. The only difference is the input and output channel — the internal processing is always the same.
