# Configuration Guide

OpenBotX uses a `config.yml` file for all configuration. All values support environment variable expansion using the `${VAR_NAME}` syntax.

## Complete Configuration Reference

### LLM Configuration

Configure the language model provider.

```yaml
llm:
  provider: "anthropic"  # Required: any PydanticAI-supported provider
  model: "claude-sonnet-4-20250514"  # Required: model name
  # Optional ModelSettings (passed to PydanticAI):
  max_tokens: 4096
  temperature: 0.7
  top_p: 1.0
  timeout: 30.0
  # Any other settings supported by PydanticAI ModelSettings
```

All fields except `provider` and `model` are passed directly to PydanticAI's `ModelSettings`.

**Supported Providers:**

PydanticAI automatically loads API keys from environment variables:

- `anthropic`: Anthropic Claude models
  - Models: `claude-sonnet-4-20250514`, `claude-opus-4-20250514`, etc
  - Environment Variable: `ANTHROPIC_API_KEY`
- `openai`: OpenAI GPT models
  - Models: `gpt-4o`, `gpt-3.5-turbo`, etc
  - Environment Variable: `OPENAI_API_KEY`
- `openrouter`: OpenRouter (access to multiple LLM providers)
  - Models: `moonshotai/kimi-k2.5`, `anthropic/claude-3.5-sonnet`, `openai/gpt-4`, etc
  - Environment Variable: `OPENROUTER_API_KEY`

Set API keys in your `.env` file:
```bash
ANTHROPIC_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
OPENROUTER_API_KEY=your_key_here
```

**OpenRouter Configuration:**

```yaml
llm:
  provider: "openrouter"
  model: "moonshotai/kimi-k2.5"  # or any model from openrouter.ai
  api_key: "${OPENROUTER_API_KEY}"
  max_tokens: 4096
  temperature: 0.7
```

**OpenAI-Compatible Endpoints:**

For custom OpenAI-compatible endpoints (like local LLMs, vLLM, LM Studio, etc):

```yaml
llm:
  provider: "openai"  # provider is ignored when base_url is set
  model: "your-model-name"
  base_url: "http://localhost:8000/v1"  # your OpenAI-compatible endpoint
  api_key: "your-api-key"  # or "dummy" if not required
  max_tokens: 4096
  temperature: 0.7
```

**Note:** When `base_url` is specified, OpenBotX uses OpenAI-compatible mode regardless of the provider value.

### Database Configuration

```yaml
database:
  type: "sqlite"  # Optional: "sqlite" (default), "postgres" or others
  path: "./db/openbotx.db"  # SQLite: path to .db file
  # Optional, for remote database:
  # host: "localhost"
  # port: 5432
  # database: "openbotx"
  # user: "openbotx"
  # password: "${POSTGRES_PASSWORD}"
```

### Storage Configuration

Configure where media and attachments are stored.

```yaml
storage:
  type: "local"  # Required: "local" or "s3"
  
  # Local filesystem settings (used when type="local")
  local:
    path: "./media"  # Optional: default "./media"
  
  # S3 settings (used when type="s3")
  s3:
    bucket: "${S3_BUCKET}"  # Required for S3
    region: "us-east-1"  # Optional: default "us-east-1"
    access_key: "${AWS_ACCESS_KEY}"  # Required for S3
    secret_key: "${AWS_SECRET_KEY}"  # Required for S3
```

### Gateway Configuration

Configure communication channels.

```yaml
gateways:
  # CLI Gateway (terminal interface)
  cli:
    enabled: true  # Optional: default true
  
  # WebSocket Gateway
  websocket:
    enabled: true  # Optional: default true
    host: "0.0.0.0"  # Optional: default "0.0.0.0"
    port: 8765  # Optional: default 8765
  
  # Telegram Gateway
  telegram:
    enabled: false  # Optional: default false
    token: "${TELEGRAM_BOT_TOKEN}"  # Required when enabled
    allowed_users: []  # Optional: list of allowed Telegram user IDs
```

### Background services

Services that run when the application starts and stop when it shuts down (same pattern as gateways and providers). Start/stop are handled in one place: `start_background_services(config)` and `stop_background_services()`.

Currently:
- **relay** – browser relay for the Chrome extension (see below).

### Browser Relay (background service)

Configures the relay server used by the Chrome extension to attach tabs. When `relay.enabled` is true, the relay is started by `start_background_services` with OpenBotX (API or CLI) and stopped by `stop_background_services` on shutdown; it does not block the application.

```yaml
relay:
  enabled: false  # Optional: default false; set true to start relay with OpenBotX
  host: "127.0.0.1"  # Optional: default "127.0.0.1" (loopback only)
  port: 18792  # Optional: default 18792; must match extension options
```

When `relay.enabled` is true, start OpenBotX with `openbotx start` or `openbotx start --cli-mode`; the relay runs in the background. Set the same port in the extension options, then click the toolbar button to attach a tab.

### Transcription Configuration

Configure audio-to-text conversion.

```yaml
transcription:
  provider: "whisper"  # Required: "whisper", etc
  model: "base"  # Required: model size ("tiny", "base", "small", "medium", "large")
```

**Supported Providers:**
- `whisper`: OpenAI Whisper (faster-whisper)
  - Models: `tiny`, `base`, `small`, `medium`, `large`, `large-v2`, `large-v3`

### Text-to-Speech Configuration

```yaml
tts:
  provider: "openai"  # Required: "openai", "edge", etc
  voice: "alloy"  # Required: voice identifier
```

**Supported Providers:**
- `openai`: OpenAI TTS API
  - Voices: `alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer`
- `edge`: Microsoft Edge TTS (free)
  - Voices: `en-US-AriaNeural`, `en-US-GuyNeural`, etc

### API Server Configuration

```yaml
api:
  host: "0.0.0.0"  # Optional: default "0.0.0.0"
  port: 8000  # Optional: default 8000
  debug: false  # Optional: default false
```

### MCP (Model Context Protocol) Configuration

```yaml
mcp:
  servers:
    - name: "filesystem"
      command: "mcp-server-filesystem"
      args: ["--path", "/path/to/files"]
      env:
        KEY: "value"
```

### Security Configuration

```yaml
security:
  prompt_injection_detection: true  # Optional: default true
  tool_approval_required: false  # Optional: default false
  max_tokens_per_request: 100000  # Optional: default 100000
  allowed_tools: []  # Optional: whitelist of allowed tools
  denied_tools: []  # Optional: blacklist of denied tools
```

### Logging Configuration

```yaml
logging:
  level: "info"  # Optional: "debug", "info", "warning", "error" (default: "info")
  format: "json"  # Optional: "json" or "text" (default: "json")
  file: "./logs/openbotx.log"  # Optional: default "./logs/openbotx.log"
  max_size_mb: 100  # Optional: default 100
  backup_count: 5  # Optional: default 5
```

### Paths Configuration

```yaml
paths:
  skills: "./skills"    # Optional: default "./skills"
  memory: "./memory"    # Optional: default "./memory"
  media: "./media"      # Optional: default "./media"
  logs: "./logs"       # Optional: default "./logs"
  db: "./db"           # Optional: default "./db"
  workspace: ""        # Optional: workspace dir for bootstrap files (nanobot-style). If set, AGENTS.md, SOUL.md, USER.md, TOOLS.md, IDENTITY.md are loaded into the system prompt.
```

#### Where to put workspace files (in your application)

OpenBotX is a Python tool you use inside **your** application. Paths under `paths` are relative to the process working directory when it runs (typically the project root where `config.yml` lives).

**Typical project layout:**

```
my-app/                    # your project root (where you run openbotx)
├── config.yml             # here you set paths.workspace
├── .env
├── workspace/             # folder you create for bootstrap files
│   ├── AGENTS.md          # agent instructions (optional)
│   ├── SOUL.md            # personality/values (optional)
│   ├── USER.md            # user context (optional)
│   ├── TOOLS.md           # tool usage guidelines (optional)
│   └── IDENTITY.md        # extra identity (optional)
├── skills/                # openbotx skills (paths.skills)
├── memory/
└── ...
```

In your application's `config.yml`:

```yaml
paths:
  workspace: "./workspace"   # relative to project root (where config.yml is)
  # or absolute path:
  # workspace: "/home/you/my-app/workspace"
```

- Create the `workspace` folder (or another name) at **your application root** (next to `config.yml`).
- Put inside only the files you want to use; you don't need all of them. The agent loads whatever is present.
- If `paths.workspace` is empty or the folder doesn't exist, bootstrap is skipped and the agent uses only the default system prompt.

### Memory (Vector Index)

Memory is always enabled. OpenBotX uses a single memory system: local embeddings (sentence-transformers) and tiktoken for chunking. No remote embedding API.

| Environment variable | Description | Default |
|----------------------|-------------|---------|
| `OPENBOTX_MEMORY_DB_PATH` | SQLite path for memory index | `data/memory.db` |
| `OPENBOTX_MEMORY_PATHS` | Comma-separated paths to index (e.g. `./memory,./docs`) | (none) |
| `OPENBOTX_EMBEDDING_MODEL` | sentence-transformers model name | `all-MiniLM-L6-v2` |
| `OPENBOTX_CHUNK_SIZE` | Chunk size in tokens | `500` |
| `OPENBOTX_CHUNK_OVERLAP` | Overlap between chunks in tokens | `50` |

Requires: `sentence-transformers`, `tiktoken`. Hybrid search (vector + full-text) is always used. With the `sqlite-vec` loadable extension, vector search uses the index (fast); without it, vector search runs in memory over stored embeddings.

### Bot Identity Configuration

```yaml
bot:
  name: "OpenBotX"  # Optional: default "OpenBotX"
  description: "Personal AI Assistant"  # Optional
```

## Environment Variables

Create a `.env` file in your project directory with your secrets:

```bash
# LLM API Keys (choose based on your provider)
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
OPENROUTER_API_KEY=sk-or-v1-...

# Storage (if using S3)
S3_BUCKET=my-bucket
AWS_ACCESS_KEY=AKIA...
AWS_SECRET_KEY=...

# Telegram (if using Telegram gateway)
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
```

## Minimal Configuration Example

```yaml
version: "1.0.0"

llm:
  provider: "anthropic"
  model: "claude-sonnet-4-20250514"
  api_key: "${ANTHROPIC_API_KEY}"

database:
  type: "sqlite"

storage:
  type: "local"

gateways:
  cli:
    enabled: true
```

This is all you need to get started!
