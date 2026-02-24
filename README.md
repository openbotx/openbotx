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
    OpenBotX is an open-source AI assistant platform with a web interface, task board, multi-channel support, and a skills system — all manageable through the browser.
</p>

## Features

- **Web Interface** — Chat, task board (Kanban), file manager, settings, all in one place
- **Multi-Channel** — Web, Telegram (more coming)
- **Task Board** — Real-time Kanban view of agent tasks (TODO / DOING / DONE / ERROR)
- **Skills System** — Define AI capabilities with Markdown files
- **Tools** — File operations, shell, web search, HTTP client, browser automation, and more
- **Multiple Agents** — Configure named agents with different models and parameters
- **Scheduler** — Cron jobs and one-time scheduled tasks
- **Multi-Provider** — Anthropic, OpenAI, OpenRouter, Gemini, DeepSeek, Groq, and custom endpoints via LiteLLM
- **Subagents** — Spawn background agents for parallel tasks
- **Memory** — Automatic conversation memory with consolidation

## Quick Start

**Requirements:** Python 3.11-3.13 and [uv](https://github.com/astral-sh/uv)

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

Detailed documentation is available in the [docs/](docs/) folder:

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
