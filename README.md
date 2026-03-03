# OpenBotX

<p align="center">
    <a href="https://github.com/openbotx/openbotx" target="_blank" rel="noopener noreferrer">
        <img width="280" src="https://raw.githubusercontent.com/openbotx/openbotx/main/extras/images/logo.png" alt="OpenBotX Logo">
    </a>
</p>

<p align="center">
    <a href="https://pypi.org/project/openbotx/"><img src="https://img.shields.io/pypi/v/openbotx?color=brightgreen&style=flat-square" alt="PyPI version"></a>
    <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11%2B-blue?style=flat-square" alt="Python 3.11+"></a>
    <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/license-MIT-yellow?style=flat-square" alt="License: MIT"></a>
</p>

<p align="center">
    <a href="https://github.com/openbotx/openbotx/actions/workflows/build.yml"><img src="https://img.shields.io/github/actions/workflow/status/openbotx/openbotx/build.yml?style=flat-square" alt="Build status"></a>
</p>

<p align="center">
    An open-source platform for orchestrating AI agents.<br>
    One command to start. Everything from the browser. No coding required.
</p>

---

## What is OpenBotX?

OpenBotX lets you create and manage AI agents from a web control panel. Chat, assign tasks, automate workflows, and monitor everything in real time — from your phone, tablet, or computer.

- **One command to start** — no Docker, no infrastructure
- **Multi-agent** — multiple agents with independent models, tools, and workspaces
- **Real-time task board** — Kanban view with live status across all agents
- **Skills system** — extend agents with Markdown files, no coding needed
- **Marketplace** — browse and install community skills directly from the web UI
- **Built-in tools** — file ops, shell, web search, HTTP client, browser automation, RSS, scheduler, and more
- **Multi-channel** — web and Telegram, same pipeline
- **Any LLM provider** — Anthropic, OpenAI, Google, OpenRouter, or any OpenAI-compatible endpoint
- **Secure** — sandboxed workspaces, shell safety guards, JWT auth

## Quick Start

**Requirements:** Python 3.11+ and [UV](https://github.com/astral-sh/uv).

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

## One-Click Deploy

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/openbotx/openbotx)
[![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://www.heroku.com/deploy?template=https://github.com/openbotx/openbotx)
[![Deploy to DigitalOcean](https://www.deploytodo.com/do-btn-blue.svg)](https://cloud.digitalocean.com/apps/new?repo=https://github.com/openbotx/openbotx/tree/main)

See the [deploy docs](docs/deploy.md) for details on each platform.

## From Source

```bash
git clone https://github.com/openbotx/openbotx.git
cd openbotx
make setup
source .venv/bin/activate
openbotx start
```

## Documentation

- [About](docs/about.md) — Project overview, features and comparison
- [Execution Flow](docs/flow.md) — Complete agent execution flow
- [Architecture](docs/architecture.md) — System design and components
- [Configuration](docs/configuration.md) — Full config.yml reference
- [API Reference](docs/api.md) — REST API and WebSocket endpoints
- [Skills](docs/skills.md) — Creating and managing skills
- [Tools](docs/tools.md) — Built-in tools reference
- [Deploy](docs/deploy.md) — One-click deploy

## License

MIT — see [LICENSE](LICENSE) for details.

## Links

- [GitHub](https://github.com/openbotx/openbotx) · [PyPI](https://pypi.org/project/openbotx/) · [Template Starter](https://github.com/openbotx/template-starter)
- [Issues](https://github.com/openbotx/openbotx/issues) · [Discussions](https://github.com/openbotx/openbotx/discussions)

Made with ❤️ by [Paulo Coutinho](https://github.com/paulocoutinhox)
