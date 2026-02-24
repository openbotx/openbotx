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

# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------
# A dictionary of named agent configurations. Each key is an arbitrary name
# (e.g. "main", "researcher", "coder"). You must define at least one agent.
agents:
  main:                           # Agent name (used as identifier).
    workspace: "./workspace"      # str  -- Working directory for this agent's files.
    model: "anthropic/claude-sonnet-4-20250514"  # str  -- Model identifier in "provider/model" format.
    params:
      max_tokens: 8192            # int  -- Maximum tokens in the model response.
      temperature: 0.1            # float -- Sampling temperature (0.0 = deterministic, higher = more creative).
      max_iterations: 40          # int  -- Maximum agentic loop iterations per request.
      memory_window: 100          # int  -- Number of recent messages to keep in context.

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
  restrict_to_workspace: true     # bool -- When true, file-related tools are restricted to the agent's workspace directory.

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
# Cron
# ---------------------------------------------------------------------------
cron:
  enabled: true                   # bool -- Enable or disable the built-in cron scheduler.
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

Define several agents, each with a different model and tuning, for specialized tasks.

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
    params:
      max_tokens: 8192
      temperature: 0.1
      max_iterations: 40
      memory_window: 100

  researcher:
    workspace: "./workspace/research"
    model: "openai/gpt-4o"
    params:
      max_tokens: 4096
      temperature: 0.3
      max_iterations: 20
      memory_window: 50

  coder:
    workspace: "./workspace/code"
    model: "deepseek/deepseek-coder"
    params:
      max_tokens: 16384
      temperature: 0.0
      max_iterations: 60
      memory_window: 80
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
- **Workspace isolation.** When `tools.restrict_to_workspace` is `true`, file operations performed by the agent are confined to its configured `workspace` directory. Disable this only if you understand the security implications.
- **Cron scheduler.** The cron system is enabled by default. Disable it with `cron.enabled: false` if you do not need scheduled tasks.
- **Model identifier format.** The `model` field in agent configurations uses the format `provider/model-name`. The prefix before the slash must match a key defined under `providers`.
