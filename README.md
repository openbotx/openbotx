# OpenBotX

<p align="center">
    <a href="https://github.com/openbotx/openbotx" target="_blank" rel="noopener noreferrer">
        <img width="280" src="extras/images/logo.png" alt="OpenBotX Logo">
    </a>
</p>

<p align="center">
    <a href="https://badge.fury.io/py/openbotx"><img src="https://badge.fury.io/py/openbotx.svg" alt="PyPI version"></a>
    <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11--3.13-blue.svg" alt="Python 3.11-3.13"></a>
    <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
</p>

<p align="center">
    <a href="https://github.com/openbotx/openbotx/actions/workflows/build.yml"><img src="https://github.com/openbotx/openbotx/actions/workflows/build.yml/badge.svg" alt="Build status"></a>
</p>

<p align="center">
    An open-source platform for orchestrating AI agents — secure, simple, and built for everyone.<br>
    Multi-agent, real-time task board, web control panel, skills system, browser automation, multi-provider, scheduler, and more.<br>
    One command to start. Everything from the browser. No coding required.
</p>

---

## What is OpenBotX?

OpenBotX is a platform for creating, managing, and orchestrating AI agents and their subagents. Everything runs from a single web control panel that works on your phone, tablet, or computer.

**The mission is simple:** let anyone — even non-developers — build AI agents, automations, and workflows that do real work, without complex setups or coding.

### Why OpenBotX?

- **One command to start.** Install, init, start. No Docker, no infrastructure, no complex configuration. Your control panel is ready in seconds.
- **Security first.** Agents run in sandboxed workspaces with restricted file access, shell safety guards, and per-agent isolation. This isn't an afterthought — it's built into the foundation.
- **Everything from the browser.** Chat, files, skills, tools, agents, scheduler, settings — all managed through a responsive web panel. No terminal required after the initial setup.
- **Real-time task board.** A Kanban board shows every task across all agents. See what's running, what finished, what failed — with live tool execution status and duration timers.
- **Multi-agent with full visibility.** Run multiple specialized agents, each with its own model, workspace, and tools. Filter and monitor what each one is doing in real time.
- **Built for non-developers.** Skills are Markdown files. Configuration is YAML with a visual editor. The goal is to make AI accessible to everyone.

## Features

### Control Panel (Web)

- Responsive interface — works on desktop, tablet, and smartphone
- Real-time chat with session management and conversation history
- Kanban task board with live tool execution status, duration timers, error details, and per-agent filtering
- File manager with Markdown editor, text editor, media preview (image/video/audio), file upload, and folder management
- Skills editor — view, create, and edit agent skills directly from the browser
- Tools viewer with parameter schema documentation
- Scheduler manager for cron jobs and one-time tasks
- System info panel (OS, CPU, memory, disk, GPU, Python and OpenBotX versions)
- Full configuration editor with YAML validation, organized in visual tabs (Bot, Channels, Storage, Tools, Auth, Advanced)

### Agents

- Multi-agent orchestration — named agents with independent models, workspaces, tools, and instructions
- Automatic LLM-based message routing between agents (classifier with conversation continuity)
- Subagents — spawn background agents for parallel tasks with isolated browser tabs and restricted tool access
- Per-agent workspace isolation and tool whitelisting
- Configurable model parameters per agent (temperature, max tokens, max iterations)

### Tools

- **File operations** — read, write, edit, and list directories (with workspace sandboxing)
- **Shell execution** — run commands with timeout, safety guards, and path restrictions
- **Web search** — Brave Search API integration
- **Web fetch** — extract content from URLs
- **HTTP client** — GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS with download/upload support
- **RSS reader** — RSS 2.0 and Atom feed parsing
- **Browser automation** — Chrome headless via CDP, multi-tab architecture, navigate, click, type, screenshot, evaluate JavaScript
- **Image generation** — configurable provider and model
- **Twitter/X posting** — text, media, and threads via OAuth 1.0a
- **Message** — send intermediate messages to the user during processing
- **Spawn** — delegate tasks to background subagents
- **Cron** — create, list, and remove scheduled jobs
- **Save memory** — persist facts to long-term memory

### Channels

- Web (WebSocket with real-time events)
- Telegram (polling, media support, typing indicator, message splitting)
- Unified message bus — all channels share the same processing pipeline

### AI Providers

- Anthropic, OpenAI, OpenRouter, Gemini, DeepSeek, Groq, and custom endpoints via LiteLLM
- Prompt caching support (Anthropic, OpenRouter)
- Extended thinking / reasoning content support

### Memory and Sessions

- Automatic conversation consolidation (long-term memory + timestamped history)
- Per-session JSONL persistence with in-memory caching
- Transient live state for real-time tool tracking (survives page refresh during execution)
- Configurable memory window for consolidation threshold

### Skills

- Markdown-based skill definitions with YAML frontmatter
- Always-on or on-demand activation
- Dependency checks (required binaries and environment variables)
- Built-in and project-level skills (project overrides built-in)
- Create and edit skills from the web panel

### Scheduler and Heartbeat

- Cron expressions, fixed intervals, and one-time scheduled tasks
- Persistent job storage with automatic origin tracking
- Heartbeat service — periodic agent wake-up from a user-managed Markdown task file

### Storage

- Local filesystem or AWS S3
- Date-organized media storage (YYYY/MM/DD)
- Public file serving without authentication
- Data URI generation for LLM image processing

### Security

- JWT authentication with configurable credentials
- Sandboxed workspaces with per-agent directory restrictions
- Shell safety guards (blocked destructive commands, path traversal protection)
- Tool access control (subagents have restricted tool sets)

## Quick Start

**Requirements:** Python 3.11-3.13 and UV [https://github.com/astral-sh/uv](https://github.com/astral-sh/uv).

```bash
# Install
uv tool install openbotx

# Create a project
mkdir my-assistant && cd my-assistant
openbotx init

# Configure API keys
cp .env.example .env
nano .env  # add your ANTHROPIC_API_KEY or other provider key

# Start
openbotx start
```

Your browser opens at `http://localhost:8000`. Log in with `admin` / `admin`.

## From Source

```bash
git clone https://github.com/openbotx/openbotx.git
cd openbotx
make setup
source .venv/bin/activate

# Frontend (optional, for development)
cd webclient && npm install && npm run build && cd ..

# Run
openbotx start
```

## CLI

```bash
openbotx init               # Create project from starter template
openbotx init --force       # Overwrite existing files
openbotx start              # Start server (opens browser)
openbotx start --no-browser # Start without opening browser
openbotx version            # Show version
```

## Documentation

Detailed documentation is available in the documentation folder:

- [Execution Flow](docs/flow.md) — Complete agent execution flow, step by step
- [Architecture](docs/architecture.md) — System design, message flow, and components
- [Configuration](docs/configuration.md) — Complete config.yml reference
- [API Reference](docs/api.md) — REST API and WebSocket endpoints
- [Skills](docs/skills.md) — Creating and managing skills
- [Tools](docs/tools.md) — Built-in tools reference

## License

MIT License — see [LICENSE](LICENSE) for details.

## Links

- [GitHub](https://github.com/openbotx/openbotx)
- [PyPI](https://pypi.org/project/openbotx/)
- [Template Starter](https://github.com/openbotx/template-starter)

## Support

- **Issues**: [GitHub Issues](https://github.com/openbotx/openbotx/issues)
- **Discussions**: [GitHub Discussions](https://github.com/openbotx/openbotx/discussions)

Made with ❤️ by [Paulo Coutinho](https://github.com/paulocoutinhox)
