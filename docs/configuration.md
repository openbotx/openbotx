# Configuration Reference

OpenBotX is configured through a `config.yml` file located in the project root directory. This document describes every configuration section, field, default value, and provides practical examples.

---

## Environment Variables

Environment variables can be referenced anywhere in `config.yml` using the `${VAR_NAME}` syntax. OpenBotX automatically loads a `.env` file from the project directory if one is present, so you can keep secrets out of version control.

Example `.env` file:

```
ANTHROPIC_API_KEY=sk-ant-...
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
AUTH_SECRET=my-secret-key
```

Referencing them in `config.yml`:

```yaml
providers:
  anthropic:
    api_key: ${ANTHROPIC_API_KEY}

channels:
  telegram:
    token: ${TELEGRAM_BOT_TOKEN}

auth:
  secret_key: ${AUTH_SECRET}
```

---

## Complete YAML Reference

Below is the full configuration schema with every field, its type, default value, and a description.

```yaml
# ---------------------------------------------------------------------------
# Bot
# ---------------------------------------------------------------------------
bot:
  name: "OpenBotX"                # str  -- Display name of the bot.
  description: "Your personal AI assistant"  # str  -- Short description shown in the UI and metadata.

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------
server:
  host: "0.0.0.0"                 # str  -- Bind address for the HTTP server.
  port: 8000                      # int  -- Port the server listens on.
  public_url: ""                  # str  -- Public URL for external access. Used for generating file URLs, opening the browser, and injected into the agent's system prompt so it knows its own base URL. Falls back to http://localhost:{port} if empty.

# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------
# A dictionary of named agent configurations. Each key is an arbitrary name
# (e.g. "main", "researcher", "coder"). You must define at least one agent.
# The first agent in the dictionary is the default agent.
agents:
  main:                           # Agent name (used as identifier).
    workspace: "./workspace"      # str  -- Working directory for this agent's files. Resolved relative to the project root. Empty or null defaults to "./workspace".
    model: "anthropic/claude-sonnet-4-20250514"  # str  -- Model identifier in "provider/model" format.
    description: ""               # str  -- Short description of this agent's purpose. Used by the AgentClassifier to route messages when multiple agents are configured.
    instructions: ""              # str  -- Agent-specific instructions appended to the system prompt as a dedicated section. Use for behavioral rules, domain expertise, or role-specific guidelines.
    tools: []                     # list[str] -- Whitelist of tool names available to this agent. When empty (default), all tools are registered. When set, only tools whose name appears in this list are available.
    params:
      max_tokens: 8192            # int  -- Maximum tokens in the model response.
      temperature: 0.1            # float -- Sampling temperature (0.0 = deterministic, higher = more creative).
      max_iterations: 40          # int  -- Maximum agentic loop iterations per request.
      memory_window: 100          # int  -- Number of recent messages to keep in context before triggering consolidation.

# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------
# Controls the LLM-based agent classifier used when multiple agents are defined.
# The classifier analyzes the user's message and recent conversation history to
# select the best agent for each request.
classifier:
  model: ""                       # str  -- Model to use for classification. When empty, uses the default agent's model. A smaller/faster model is recommended since classification is a lightweight task.

# ---------------------------------------------------------------------------
# Image Generation
# ---------------------------------------------------------------------------
image:
  model: "gemini-3-pro-image-preview"  # str  -- Model name for image generation.
  provider:                            # ProviderConfig -- Provider connection settings (same schema as providers.*).
    name: "gemini"                     # str  -- Image generation backend (e.g. "gemini", "openai").
    api_key: ""                        # str  -- API key for the image provider.
    api_base: null                     # str | null -- Custom base URL. Set to null to use the provider's default endpoint.
    headers: {}                        # dict[str, str] -- Custom HTTP headers sent with every API request.
    options: {}                        # dict -- Additional provider-specific parameters merged into the request body.

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
auth:
  username: "admin"               # str  -- Username for the web UI login.
  password: "admin"               # str  -- Password for the web UI login.
  secret_key: ""                  # str  -- Secret used for signing tokens. Auto-generated at startup if left empty.

# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------
# A dictionary of LLM provider configurations. Each key is the provider name.
# Supported providers: custom, openrouter, anthropic, openai, deepseek, gemini, groq.
providers:
  anthropic:                      # Provider name (must match prefix used in agent model field).
    api_key: ""                   # str  -- API key for this provider.
    api_base: null                # str | null -- Custom base URL. Set to null to use the provider's default endpoint.
    headers: {}                   # dict[str, str] -- Custom HTTP headers sent with every API request.
    options: {}                   # dict -- Additional provider-specific parameters merged into the request body.

# ---------------------------------------------------------------------------
# Channels
# ---------------------------------------------------------------------------
channels:
  send_progress: true             # bool -- Send progress/status updates to the client during processing.
  send_tool_hints: false          # bool -- Send tool invocation hints to the client (useful for debugging).
  telegram:
    enabled: false                # bool -- Enable the Telegram bot integration.
    token: ""                     # str  -- Telegram Bot API token (obtain from @BotFather).
    allowed_users: []             # list[str] -- Telegram usernames or user IDs allowed to interact. Empty list allows everyone.
    proxy: null                   # str | null -- SOCKS5 or HTTP proxy URL for Telegram API requests.
    reply_to_message: false       # bool -- Whether the bot replies in-thread to the original message.

# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
tools:
  web_search:
    api_key: ""                   # str  -- Brave Search API key for the web search tool.
    max_results: 5                # int  -- Maximum number of search results to return per query.
  exec:
    timeout: 60                   # int  -- Maximum execution time in seconds for the exec tool.
  restrict_to_workspace: true     # bool -- When true, file-related tools are restricted to the agent's workspace directory and the shared public directory. When false, all filesystem paths are accessible.

# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------
storage:
  type: "local"                   # str  -- Storage backend: "local" for filesystem, "s3" for Amazon S3.
  local_path: "./workspace"       # str  -- Directory path when using local storage.
  s3_bucket: ""                   # str  -- S3 bucket name (required when type is "s3").
  s3_region: "us-east-1"         # str  -- AWS region for the S3 bucket.
  s3_access_key: ""              # str  -- AWS access key ID.
  s3_secret_key: ""              # str  -- AWS secret access key.

# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------
heartbeat:
  enabled: true                   # bool -- Enable the periodic heartbeat service.
  interval: 1800                  # int  -- Seconds between checks (default: 30 minutes).

# ---------------------------------------------------------------------------
# Cron
# ---------------------------------------------------------------------------
cron:
  enabled: true                   # bool -- Enable or disable the built-in cron scheduler.
```

---

## Agent Configuration Details

### Workspace Resolution

Each agent's workspace path is resolved at startup by `AgentConfig.resolve_workspace(project_path)`:

1. If the workspace is a relative path (e.g., `./workspace`), it is resolved relative to the **project root** (where `config.yml` lives).
2. If the workspace is an absolute path, it is used as-is.
3. `~` is expanded to the user's home directory.
4. Empty or null workspace values are automatically defaulted to `"./workspace"` by a Pydantic field validator.

The workspace directory is created automatically at startup if it does not exist.

### Workspace Restriction

When `tools.restrict_to_workspace` is `true` (the default), the `PathResolver` enforces that all file operations are confined to two directories:

1. The agent's own workspace directory.
2. The shared `public/` directory at the project root.

This means:

- File tools (`read_file`, `write_file`, `edit_file`, `list_dir`) can only access files within the workspace or public directory.
- The HTTP client's `download_path` and `upload_file` parameters are also resolved through the `PathResolver`.
- The `exec` tool's working directory is locked to the workspace.
- Attempts to access paths outside these directories raise a `PermissionError`.

When `restrict_to_workspace` is `false`, all filesystem paths are accessible without restriction.

### Tool Whitelisting

The `tools` field accepts a list of tool names. When set, only tools whose `name` property matches an entry in the list are registered for that agent. When empty (default), all tools are available.

Available tool names: `read_file`, `write_file`, `edit_file`, `list_dir`, `exec`, `web_search`, `web_fetch`, `http_client`, `rss_reader`, `browser`, `message`, `spawn`, `cron`, `save_memory`, `image_generation`.

### Agent Instructions

The `instructions` field is injected into the system prompt as a dedicated `# Agent Instructions` section, after all other context (bootstrap files, memory, skills). Use this for:

- Domain-specific behavioral rules ("Always include disclaimers for financial data")
- Role definition ("You are a market analyst specializing in cryptocurrency")
- Output formatting guidelines ("Format reports as markdown tables")

### Agent Description

The `description` field is used by the `AgentClassifier` when routing messages in multi-agent setups. It should concisely describe what the agent does so the classifier can make informed routing decisions.

### Multi-Agent Classification

When multiple agents are configured, the `Orchestrator` uses the `AgentClassifier` to route each message. The classifier:

1. Uses the model specified in `classifier.model` (or the default agent's model if empty).
2. Reads agent descriptions from the `agents` dictionary.
3. Analyzes the user's latest message plus the last 20 messages of conversation history.
4. Calls a `route(agent_name, confidence)` tool to select the best agent.
5. Falls back to the first (default) agent on error.

For single-agent setups, no classification is performed — all messages go to the default agent.

---

## Examples

### 1. Basic Setup with Anthropic

A minimal configuration using Anthropic as the sole provider.

```yaml
bot:
  name: "MyAssistant"
  description: "A helpful AI assistant"

server:
  host: "0.0.0.0"
  port: 8000

providers:
  anthropic:
    api_key: ${ANTHROPIC_API_KEY}

agents:
  main:
    model: "anthropic/claude-sonnet-4-20250514"
    params:
      max_tokens: 4096
      temperature: 0.2

auth:
  username: "admin"
  password: ${AUTH_PASSWORD}
```

### 2. OpenRouter Setup

Using OpenRouter to access models from multiple vendors through a single API key.

```yaml
providers:
  openrouter:
    api_key: ${OPENROUTER_API_KEY}

agents:
  main:
    model: "openrouter/anthropic/claude-sonnet-4-20250514"
    params:
      max_tokens: 8192
      temperature: 0.1
```

### 3. Multiple Agents

Define several agents, each with a different model, workspace, and specialization.

```yaml
providers:
  anthropic:
    api_key: ${ANTHROPIC_API_KEY}
  openai:
    api_key: ${OPENAI_API_KEY}
  deepseek:
    api_key: ${DEEPSEEK_API_KEY}

agents:
  main:
    workspace: "./workspace"
    model: "anthropic/claude-sonnet-4-20250514"
    description: "General-purpose assistant for everyday tasks"
    instructions: "You are a helpful general assistant. Route specialized requests to appropriate agents."
    params:
      max_tokens: 8192
      temperature: 0.1
      max_iterations: 40
      memory_window: 100

  researcher:
    workspace: "./workspace/research"
    model: "openai/gpt-4o"
    description: "Research specialist for deep analysis and information gathering"
    instructions: "Focus on thorough research. Cite sources when possible. Save findings to reports."
    tools: [read_file, write_file, edit_file, list_dir, exec, web_search, web_fetch, http_client, rss_reader, browser, message, save_memory]
    params:
      max_tokens: 4096
      temperature: 0.3
      max_iterations: 20
      memory_window: 50

  coder:
    workspace: "./workspace/code"
    model: "deepseek/deepseek-coder"
    description: "Code specialist for programming tasks"
    instructions: "Write clean, well-structured code. Always test your changes."
    tools: [read_file, write_file, edit_file, list_dir, exec, web_search, web_fetch, message]
    params:
      max_tokens: 16384
      temperature: 0.0
      max_iterations: 60
      memory_window: 80

classifier:
  model: "anthropic/claude-haiku-3"  # use a fast model for classification
```

### 4. Telegram Channel

Enable the Telegram bot and restrict access to specific users.

```yaml
channels:
  send_progress: true
  send_tool_hints: false
  telegram:
    enabled: true
    token: ${TELEGRAM_BOT_TOKEN}
    allowed_users:
      - "alice"
      - "bob"
      - "123456789"
    proxy: "socks5://127.0.0.1:1080"
    reply_to_message: true
```

### 5. S3 Storage

Use Amazon S3 as the storage backend instead of the local filesystem.

```yaml
storage:
  type: "s3"
  s3_bucket: "my-openbotx-storage"
  s3_region: "eu-west-1"
  s3_access_key: ${AWS_ACCESS_KEY_ID}
  s3_secret_key: ${AWS_SECRET_ACCESS_KEY}
```

### 6. Environment Variable References

A comprehensive example showing `${VAR_NAME}` references throughout the configuration. All values below are resolved at startup from the `.env` file or the shell environment.

```yaml
bot:
  name: ${BOT_NAME}
  description: ${BOT_DESCRIPTION}

server:
  host: ${SERVER_HOST}
  port: 8000

providers:
  anthropic:
    api_key: ${ANTHROPIC_API_KEY}
  gemini:
    api_key: ${GEMINI_API_KEY}

agents:
  main:
    workspace: ${AGENT_WORKSPACE}
    model: "anthropic/claude-sonnet-4-20250514"

image:
  model: "gemini-3-pro-image-preview"
  provider:
    name: "gemini"
    api_key: ${GEMINI_API_KEY}

auth:
  username: ${AUTH_USERNAME}
  password: ${AUTH_PASSWORD}
  secret_key: ${AUTH_SECRET_KEY}

channels:
  telegram:
    enabled: true
    token: ${TELEGRAM_BOT_TOKEN}

tools:
  web_search:
    api_key: ${BRAVE_SEARCH_API_KEY}

storage:
  type: "s3"
  s3_bucket: ${S3_BUCKET}
  s3_region: ${S3_REGION}
  s3_access_key: ${AWS_ACCESS_KEY_ID}
  s3_secret_key: ${AWS_SECRET_ACCESS_KEY}
```

Corresponding `.env` file:

```
BOT_NAME=MyAssistant
BOT_DESCRIPTION=A helpful AI assistant
SERVER_HOST=0.0.0.0
AGENT_WORKSPACE=./workspace

ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIza...

AUTH_USERNAME=admin
AUTH_PASSWORD=changeme
AUTH_SECRET_KEY=a-long-random-string

TELEGRAM_BOT_TOKEN=123456:ABC-DEF...

BRAVE_SEARCH_API_KEY=BSA...

S3_BUCKET=my-openbotx-storage
S3_REGION=us-east-1
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=wJal...
```

---

## Supported Providers

| Provider     | Key              | Description                                      |
|--------------|------------------|--------------------------------------------------|
| `anthropic`  | `anthropic`      | Anthropic (Claude models) via the native API.    |
| `openai`     | `openai`         | OpenAI (GPT models) via the native API.          |
| `openrouter` | `openrouter`     | OpenRouter proxy -- access multiple vendors.     |
| `gemini`     | `gemini`         | Google Gemini models.                            |
| `deepseek`   | `deepseek`       | DeepSeek models.                                 |
| `groq`       | `groq`           | Groq inference engine for supported models.      |
| `custom`     | `custom`         | Any OpenAI-compatible endpoint via `api_base`.   |

When using the `custom` provider, set `api_base` to the base URL of your endpoint:

```yaml
providers:
  custom:
    api_key: ${CUSTOM_API_KEY}
    api_base: "https://my-llm-server.example.com/v1"
```

---

## Notes

- **Defaults are applied automatically.** You only need to include the sections and fields you want to override. Any omitted field falls back to its default value.
- **Secret key auto-generation.** If `auth.secret_key` is left empty, a random key is generated each time the server starts. Set it explicitly if you need stable tokens across restarts.
- **Workspace isolation.** When `tools.restrict_to_workspace` is `true`, file operations performed by each agent are confined to its configured `workspace` directory and the shared `public/` directory. The `PathResolver` enforces this by checking that all resolved paths fall within one of these allowed directories. Disable this only if you understand the security implications.
- **Workspace defaulting.** If an agent's `workspace` field is empty, null, or whitespace, it automatically defaults to `"./workspace"`. This ensures every agent always has a valid workspace.
- **Per-agent workspaces.** Each agent can have its own workspace directory. Workspaces are created automatically at startup. In multi-agent setups, this provides natural isolation between agents.
- **Cron scheduler.** The cron system is enabled by default. Disable it with `cron.enabled: false` if you do not need scheduled tasks.
- **Heartbeat service.** When enabled, the agent periodically reads `HEARTBEAT.md` from the workspace for tasks. Results are stored in a dedicated `heartbeat` session, accessible from the web interface session list. Set `heartbeat.enabled: false` to disable.
- **Model identifier format.** The `model` field in agent configurations uses the format `provider/model-name`. The prefix before the slash must match a key defined under `providers`.
- **Classifier model.** In multi-agent setups, use `classifier.model` to specify a fast/cheap model for message classification. The classifier only needs to select an agent, not generate full responses, so a smaller model reduces cost and latency.
