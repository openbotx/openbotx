# Configuration Reference

OpenBotX is configured through a `config.yml` file located in the project root directory. This document describes every configuration section, field, default value, and provides practical examples.

---

## Environment Variables

Environment variables can be referenced anywhere in `config.yml` using the `${VAR_NAME}` syntax. OpenBotX automatically loads a `.env` file from the project directory if one is present, so you can keep secrets out of version control.

Example `.env` file:

```
ANTHROPIC_API_KEY=sk-ant-...
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
```

Referencing them in `config.yml`:

```yaml
credentials:
  anthropic:
    type: simple
    key: ${ANTHROPIC_API_KEY}
  telegram:
    type: simple
    key: ${TELEGRAM_BOT_TOKEN}
  web_client:
    type: login
    username: admin
    password: changeme
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
  credential: ""                  # str  -- Name of a credential (type: simple) whose key is used as the JWT signing secret. If not configured, a default simple credential with a random key is auto-created at startup.

# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------
# A dictionary of named agent configurations. Each key is an arbitrary name
# (e.g. "main", "researcher", "coder"). You must define at least one agent.
# The first agent in the dictionary is the default agent.
agents:
  main:                           # Agent name (used as identifier).
    workspace: "./workspace"      # str  -- Working directory for this agent's files. Resolved relative to the project root. Empty or null defaults to "./workspace".
    model: ""                       # str  -- Model identifier in "provider/model" format (required).
    description: ""               # str  -- Short description of this agent's purpose. Used by the AgentClassifier to route messages when multiple agents are configured.
    instructions: ""              # str  -- Agent-specific instructions appended to the system prompt as a dedicated section. Use for behavioral rules, domain expertise, or role-specific guidelines.
    tools: []                     # list[str] -- Whitelist of tool names available to this agent. When empty (default), all tools are registered. When set, only tools whose name appears in this list are available.
    denied_tools: []              # list[str] -- Denylist of tool names to exclude from this agent. Applied on top of the whitelist. Useful for selectively blocking dangerous tools without listing all allowed ones.
    model_params: {}                # dict -- Arbitrary model parameters passed to the LLM provider. Common keys: max_tokens, temperature, top_p, etc. Empty by default.
    agent_params:
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
# Credentials
# ---------------------------------------------------------------------------
# A dictionary of named credentials. Each key is a name you choose
# (e.g. "anthropic", "web_client", "twitter", "s3"). The `type` field
# determines which fields are relevant. Other sections reference these by
# name via their `credential` field.
#
# Supported types: simple, oauth1, basic, login, aws.
credentials:
  anthropic:                      # Credential name (referenced by providers, channels, etc.).
    type: "simple"                # str  -- Credential type.
    key: ""                       # str  -- API key or token.
  # web_client:
  #   type: login
  #   username: ""                # str  -- Username for the web UI login.
  #   password: ""                # str  -- Password for the web UI login.
  # twitter:
  #   type: oauth1
  #   consumer_key: ""
  #   consumer_secret: ""
  #   access_token: ""
  #   access_token_secret: ""

# ---------------------------------------------------------------------------
# Image Generation
# ---------------------------------------------------------------------------
image:
  model: ""                            # str  -- Model in "provider/model" format (e.g. "openai/dall-e-3"). Provider is resolved from the prefix, same as agents.

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
web_client:
  credential: ""                  # str  -- Name of a credential (type: login) for web UI login. Leave empty to disable authentication; a default login credential (admin/admin) is auto-created at startup if not configured.

# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------
# A dictionary of LLM provider configurations. Each key is the provider name.
# Supported providers: custom, openrouter, anthropic, openai, deepseek, gemini, groq.
# Credentials are not stored here -- each provider references a credential by name.
providers:
  anthropic:                      # Provider name (must match prefix used in agent model field).
    credential: ""                # str  -- Name of the credential that holds the API key for this provider.
    base_url: ""                  # str  -- Custom base URL. Leave empty to use the provider's default endpoint. Used for OpenAI-compatible APIs, self-hosted models, or proxies.
    request_headers: {}           # dict[str, str] -- Custom HTTP headers sent with every API request.
    request_options: {}           # dict -- Additional provider-specific parameters merged into the request body.
    model_params: {}              # dict -- Default model parameters for all agents using this provider. Agent-level model_params override these. Empty by default. Supports "context_window" to override the built-in context limit for compaction (e.g. context_window: 64000).


# ---------------------------------------------------------------------------
# Channels
# ---------------------------------------------------------------------------
channels:
  send_progress: true             # bool -- Send progress/status updates to the client during processing.
  send_tool_hints: false          # bool -- Send tool invocation hints to the client (useful for debugging).
  telegram:
    enabled: false                # bool -- Enable the Telegram bot integration.
    credential: ""                # str  -- Name of a credential (type: simple) that holds the Telegram Bot API token.
    allowed_users: []             # list[str] -- Telegram usernames or user IDs allowed to interact. Empty list allows everyone.
    proxy: null                   # str | null -- SOCKS5 or HTTP proxy URL for Telegram API requests.
    reply_to_message: false       # bool -- Whether the bot replies in-thread to the original message.

# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
tools:
  general:
    restrict_to_workspace: true   # bool -- When true, file-related tools are restricted to the agent's workspace directory and the shared public directory. When false, all filesystem paths are accessible.
  exec:
    timeout: 60                   # int  -- Maximum execution time in seconds for the exec tool.
  web_search:
    credential: ""                # str  -- Name of a credential (type: simple) that holds the Brave Search API key.
    max_results: 5                # int  -- Maximum number of search results to return per query.

# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------
storage:
  type: "local"                   # str  -- Storage backend: "local" for filesystem, "s3" for Amazon S3.
  local_path: "./workspace"       # str  -- Directory path when using local storage.
  s3_bucket: ""                   # str  -- S3 bucket name (required when type is "s3").
  s3_region: ""                  # str  -- AWS region for the S3 bucket (required when type is "s3").
  credential: ""                 # str  -- Name of a credential (type: aws) that holds AWS credentials.

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

When `tools.general.restrict_to_workspace` is `true` (the default), the `PathResolver` enforces that all file operations are confined to two directories:

1. The agent's own workspace directory.
2. The shared `public/` directory at the project root.

This means:

- File tools (`read_file`, `write_file`, `edit_file`, `list_dir`) can only access files within the workspace or public directory.
- The HTTP client's `download_path` and `upload_file` parameters are also resolved through the `PathResolver`.
- The `exec` tool's working directory is locked to the workspace.
- Attempts to access paths outside these directories raise a `PermissionError`.

When `restrict_to_workspace` is `false`, all filesystem paths are accessible without restriction.

### Tool Whitelisting and Denylisting

The `tools` field accepts a list of tool names as a **whitelist**. When set, only tools whose `name` property matches an entry in the list are registered for that agent. When empty (default), all tools are available.

The `denied_tools` field accepts a list of tool names as a **denylist**. Tools in this list are excluded from the agent regardless of the whitelist. This is useful for selectively blocking dangerous tools without needing to enumerate all allowed ones.

Both filters are combined in `build_registry()`: a tool is registered only if it passes the whitelist (if set) AND is not in the denylist. Subagents additionally have a hardcoded denylist (`spawn`, `message`, `memory_save`, `memory_read`, `memory_search`, `cron`) that is combined with the agent's `denied_tools`.

Available tool names: `read_file`, `write_file`, `edit_file`, `list_dir`, `exec`, `web_search`, `web_fetch`, `http_client`, `rss_reader`, `browser`, `message`, `spawn`, `cron`, `memory_save`, `memory_read`, `memory_search`, `generate_image`.

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

### Model Parameters Resolution

Model parameters are flexible dictionaries passed directly to the LLM provider. Any key-value pair supported by the underlying model API can be used (e.g., `max_tokens`, `temperature`, `top_p`, `frequency_penalty`). Resolution order:

1. **Provider `model_params`** — default parameters for all agents using the provider
2. **Agent `model_params`** — override provider defaults for this specific agent

At startup, `ServerFactory.create_orchestrator` merges provider defaults with agent overrides using simple dict merge (`{**provider_params, **agent_params}`). Agent-level keys always take precedence.

Example:

```yaml
credentials:
  anthropic:
    type: simple
    key: ${ANTHROPIC_API_KEY}

providers:
  anthropic:
    credential: anthropic
    model_params:
      max_tokens: 16384
      temperature: 0.2

agents:
  main:
    model: "anthropic/claude-sonnet-4-20250514"
    model_params:
      max_tokens: 8192           # Overrides provider → effective: 8192
      # temperature not set      → inherits 0.2 from provider

  researcher:
    model: "anthropic/claude-sonnet-4-20250514"
    # model_params not set       → inherits all from provider
```

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

credentials:
  anthropic:
    type: simple
    key: ${ANTHROPIC_API_KEY}
  web_client:
    type: login
    username: "admin"
    password: ${AUTH_PASSWORD}

providers:
  anthropic:
    credential: anthropic

agents:
  main:
    model: "anthropic/claude-sonnet-4-20250514"
    model_params:
      max_tokens: 4096
      temperature: 0.2

web_client:
  credential: web_client
```

### 2. OpenRouter Setup

Using OpenRouter to access models from multiple vendors through a single API key.

```yaml
credentials:
  openrouter:
    type: simple
    key: ${OPENROUTER_API_KEY}

providers:
  openrouter:
    credential: openrouter

agents:
  main:
    model: "openrouter/anthropic/claude-sonnet-4-20250514"
    model_params:
      max_tokens: 8192
      temperature: 0.1
```

### 3. Multiple Agents

Define several agents, each with a different model, workspace, and specialization.

```yaml
credentials:
  anthropic:
    type: simple
    key: ${ANTHROPIC_API_KEY}
  openai:
    type: simple
    key: ${OPENAI_API_KEY}
  deepseek:
    type: simple
    key: ${DEEPSEEK_API_KEY}

providers:
  anthropic:
    credential: anthropic
  openai:
    credential: openai
  deepseek:
    credential: deepseek

agents:
  main:
    workspace: "./workspace"
    model: "anthropic/claude-sonnet-4-20250514"
    description: "General-purpose assistant for everyday tasks"
    instructions: "You are a helpful general assistant. Route specialized requests to appropriate agents."
    model_params:
      max_tokens: 8192
      temperature: 0.1
    agent_params:
      max_iterations: 40
      memory_window: 100

  researcher:
    workspace: "./workspace/research"
    model: "openai/gpt-4o"
    description: "Research specialist for deep analysis and information gathering"
    instructions: "Focus on thorough research. Cite sources when possible. Save findings to reports."
    tools: [read_file, write_file, edit_file, list_dir, exec, web_search, web_fetch, http_client, rss_reader, browser, message, memory_save, memory_read, memory_search]
    model_params:
      max_tokens: 4096
      temperature: 0.3
    agent_params:
      max_iterations: 20
      memory_window: 50

  coder:
    workspace: "./workspace/code"
    model: "deepseek/deepseek-coder"
    description: "Code specialist for programming tasks"
    instructions: "Write clean, well-structured code. Always test your changes."
    tools: [read_file, write_file, edit_file, list_dir, exec, web_search, web_fetch, message]
    model_params:
      max_tokens: 16384
      temperature: 0.0
    agent_params:
      max_iterations: 60
      memory_window: 80

classifier:
  model: "anthropic/claude-haiku-3"  # use a fast model for classification
```

### 4. Telegram Channel

Enable the Telegram bot and restrict access to specific users.

```yaml
credentials:
  telegram:
    type: simple
    key: ${TELEGRAM_BOT_TOKEN}

channels:
  send_progress: true
  send_tool_hints: false
  telegram:
    enabled: true
    credential: telegram
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
credentials:
  s3:
    type: aws
    access_key: ${AWS_ACCESS_KEY_ID}
    secret_key: ${AWS_SECRET_ACCESS_KEY}

storage:
  type: "s3"
  s3_bucket: "my-openbotx-storage"
  s3_region: "eu-west-1"
  credential: s3
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

credentials:
  anthropic:
    type: simple
    key: ${ANTHROPIC_API_KEY}
  gemini:
    type: simple
    key: ${GEMINI_API_KEY}
  web_client:
    type: login
    username: ${AUTH_USERNAME}
    password: ${AUTH_PASSWORD}
  telegram:
    type: simple
    key: ${TELEGRAM_BOT_TOKEN}
  brave:
    type: simple
    key: ${BRAVE_SEARCH_API_KEY}
  twitter:
    type: oauth1
    consumer_key: ${TWITTER_CONSUMER_KEY}
    consumer_secret: ${TWITTER_CONSUMER_SECRET}
    access_token: ${TWITTER_ACCESS_TOKEN}
    access_token_secret: ${TWITTER_ACCESS_TOKEN_SECRET}
  s3:
    type: aws
    access_key: ${AWS_ACCESS_KEY_ID}
    secret_key: ${AWS_SECRET_ACCESS_KEY}

providers:
  anthropic:
    credential: anthropic
  gemini:
    credential: gemini

agents:
  main:
    workspace: ${AGENT_WORKSPACE}
    model: "anthropic/claude-sonnet-4-20250514"

image:
  model: "gemini/gemini-3-pro-image-preview"

web_client:
  credential: web_client

channels:
  telegram:
    enabled: true
    credential: telegram

tools:
  web_search:
    credential: brave

storage:
  type: "s3"
  s3_bucket: ${S3_BUCKET}
  s3_region: ${S3_REGION}
  credential: s3
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

TELEGRAM_BOT_TOKEN=123456:ABC-DEF...

BRAVE_SEARCH_API_KEY=BSA...

TWITTER_CONSUMER_KEY=...
TWITTER_CONSUMER_SECRET=...
TWITTER_ACCESS_TOKEN=...
TWITTER_ACCESS_TOKEN_SECRET=...

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
| `custom`     | `custom`         | Any OpenAI-compatible endpoint via `base_url`.   |

When using the `custom` provider, set `base_url` on the provider entry:

```yaml
credentials:
  custom:
    type: simple
    key: ${CUSTOM_API_KEY}

providers:
  custom:
    credential: custom
    base_url: "https://my-llm-server.example.com/v1"
```

---

## Notes

- **Defaults are applied automatically.** You only need to include the sections and fields you want to override. Any omitted field falls back to its default value.
- **Server credential auto-generation.** If `server.credential` is not configured, the server automatically creates a `simple` credential with a random key for JWT signing on each startup. Set it explicitly if you need stable tokens across restarts. Similarly, if `web_client.credential` is not configured, a default `login` credential with admin/admin credentials is auto-created.
- **Workspace isolation.** When `tools.general.restrict_to_workspace` is `true`, file operations performed by each agent are confined to its configured `workspace` directory and the shared `public/` directory. The `PathResolver` enforces this by checking that all resolved paths fall within one of these allowed directories. Disable this only if you understand the security implications.
- **Exec timeout.** The `tools.exec.timeout` setting controls the maximum execution time in seconds for the `exec` tool. Commands exceeding this limit are automatically killed.
- **Workspace defaulting.** If an agent's `workspace` field is empty, null, or whitespace, it automatically defaults to `"./workspace"`. This ensures every agent always has a valid workspace.
- **Per-agent workspaces.** Each agent can have its own workspace directory. Workspaces are created automatically at startup. In multi-agent setups, this provides natural isolation between agents.
- **Cron scheduler.** The cron system is enabled by default. Disable it with `cron.enabled: false` if you do not need scheduled tasks.
- **Heartbeat service.** When enabled, the agent periodically reads `HEARTBEAT.md` from the workspace for tasks. Results are stored in a dedicated `heartbeat` session, accessible from the web interface session list. Set `heartbeat.enabled: false` to disable.
- **Model identifier format.** The `model` field in agent configurations uses the format `provider/model-name`. The prefix before the slash must match a key defined under `providers`.
- **Classifier model.** In multi-agent setups, use `classifier.model` to specify a fast/cheap model for message classification. The classifier only needs to select an agent, not generate full responses, so a smaller model reduces cost and latency.
