# Skills

Skills define what the OpenBotX agent knows and how it behaves in specific contexts. They are the primary mechanism for extending the agent with specialized knowledge, workflows, and domain expertise.

## Overview

A skill is a Markdown file with YAML frontmatter that provides instructions to the AI agent. Skills transform OpenBotX from a general-purpose assistant into a specialized agent equipped with procedural knowledge for specific domains or tasks.

Skills are loaded by the `SkillsLoader` class (`openbotx/agent/skills.py`) and injected into the system prompt by the `ContextBuilder` (`openbotx/agent/context.py`).

## Skill Locations

Skills live in two directories, loaded in order:

1. **Built-in skills** -- `openbotx/skills/` inside the OpenBotX package. These ship with the platform and are always available.
2. **Project skills** -- `workspace/skills/` in the user's project directory. These are user-created and project-specific.

**Precedence rule:** Project skills override built-in skills that share the same directory name. The `SkillsLoader` iterates built-in skills first, then project skills, using the directory name as the key. A project skill with the same name replaces the built-in entry entirely.

## Directory Structure

Each skill is a directory containing a required `SKILL.md` file and optional resource subdirectories:

```
workspace/skills/
└── my-skill/
    ├── SKILL.md          (required)
    ├── scripts/          (optional - executable code)
    ├── references/       (optional - documentation for context)
    └── assets/           (optional - files used in output)
```

The directory name serves as the skill identifier. Use lowercase letters, digits, and hyphens only. Names must be under 64 characters.

## SKILL.md Format

Every `SKILL.md` file has two parts: YAML frontmatter and a Markdown body.

### Frontmatter Fields

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `name` | Yes | string | Skill identifier, used in the skills summary |
| `description` | No | string | What the skill does and when to use it. This is the primary triggering mechanism -- the agent reads this to decide whether to activate the skill |
| `always` | No | boolean | If `true`, the skill body is always included in the system prompt |
| `requires` | No | object | Runtime requirements that must be satisfied for the skill to be available |

### Requirements

The `requires` field supports two types of checks:

- **`env`** -- A list of environment variable names that must be set.
- **`bins`** -- A list of binary names that must be available on `PATH` (checked via `shutil.which`).

Both accept either a single string or a list of strings. All listed requirements must be satisfied for the skill to report as `available`. If any requirement is missing, the skill appears in the summary with `status="unavailable"`.

### Body

The Markdown body contains the actual instructions for the agent. This content is loaded into context only when the skill is activated (or always, if `always: true`). Keep the body under 500 lines to avoid context bloat.

## How Skills Are Loaded

The `SkillsLoader` manages the full lifecycle:

1. **Discovery** -- `_discover_skills()` scans both skill directories and builds a name-to-path mapping. Project skills overwrite built-in skills with the same name.

2. **Listing** -- `list_skills()` returns metadata for all discovered skills (name, description, availability, always flag). This metadata is formatted into an XML summary by `build_skills_summary()` and included in every system prompt so the agent knows what skills exist.

3. **Always-on loading** -- `get_always_skills()` returns the full body of skills marked with `always: true` (provided their requirements are met). These are injected directly into the system prompt by `ContextBuilder`.

4. **On-demand loading** -- `load_skill(name)` returns the body of a specific skill, stripped of frontmatter. This is used when the agent decides to activate a particular skill during a conversation.

### Skills Summary Format

The skills summary is injected into the system prompt as XML:

```xml
<skills>
  <skill name="memory" status="available" always="true">Two-layer memory system with grep-based recall.</skill>
  <skill name="browser" status="available">Automate browser interactions...</skill>
  <skill name="weather" status="unavailable">Get current weather data...</skill>
</skills>
```

## Built-in Skills

OpenBotX ships with eight built-in skills.

### browser

Automate browser interactions for web scraping, testing, and navigation. Controls a headless Chrome browser via CDP (Chrome DevTools Protocol) to navigate pages, interact with elements, capture screenshots, and extract content.

- **Tool:** `browser`
- **Actions:** `navigate`, `snapshot`, `click`, `type`, `evaluate`, `screenshot`, `wait`
- **Requires:** `google-chrome` binary on PATH

### cron

Schedule reminders and recurring tasks. Supports three modes: reminders (message sent directly to user), tasks (agent executes and sends result), and one-time scheduled events that auto-delete after firing.

- **Tool:** `cron`
- **Actions:** `add`, `list`, `remove`
- **Always loaded:** Yes
- **Supports:** interval-based scheduling (`every_seconds`), cron expressions (`cron_expr`), one-time scheduling (`at`), and IANA timezone awareness (`tz`)

### http-client

Make HTTP requests (GET, POST, PUT, PATCH, DELETE) to APIs and web services. Handles JSON, form-encoded, and plain text bodies, with support for Bearer tokens, Basic auth, and API key authentication.

- **Tool:** `http_client`
- **Parameters:** `method`, `url`, `headers`, `body`

### image-generation

Generate images from text descriptions using AI models. Supports configurable aspect ratios.

- **Tool:** `generate_image`
- **Parameters:** `prompt`, `output_path`, `aspect_ratio`

### memory

Two-layer memory system with grep-based recall. Manages long-term facts in `memory/MEMORY.md` (always loaded into context) and an append-only event log in `memory/HISTORY.md` (searchable via grep).

- **Always loaded:** Yes
- **Auto-consolidation:** Old conversations are automatically summarized and appended to the history file

### skill-creator

Create or update OpenBotX skills from within a conversation. Provides guidance on skill structure, naming conventions, the progressive disclosure design principle, and the full creation workflow from understanding through iteration.

### summarize

Summarize or extract text and transcripts from URLs, podcasts, YouTube videos, and local files. Uses the `summarize` CLI tool with configurable models and output lengths.

- **Requires:** `summarize` binary on PATH
- **Supports:** Multiple AI providers (OpenAI, Anthropic, Google, xAI), YouTube transcript extraction, Firecrawl fallback for blocked sites

### weather

Get current weather and forecasts using free services (no API key required). Uses wttr.in as the primary source and Open-Meteo as a JSON fallback.

- **Requires:** `curl` binary on PATH

## Context Files

In addition to skills, OpenBotX uses context files placed in the project workspace root to shape agent behavior. These are loaded by `ContextBuilder` and included in every system prompt:

| File | Purpose |
|------|---------|
| `SOUL.md` | Bot personality, tone, and behavioral guidelines |
| `USER.md` | User preferences and personalization information |
| `AGENTS.md` | Agent and subagent configuration and capabilities |
| `TOOLS.md` | Available tools documentation |

These files are optional. If present, their contents are included under a heading in the system prompt (e.g., `# SOUL.md`).

## Creating a New Skill

### Step 1: Create the directory

```
workspace/skills/my-skill/
```

### Step 2: Write SKILL.md

```markdown
---
name: my-skill
description: A clear description of what this skill does and when to use it
---

# My Skill

Instructions for the agent when this skill is activated.

## When to Use
Describe the triggers and contexts.

## Steps
1. First action
2. Second action

## Response Format
Guidelines for output formatting.
```

### Step 3: Add resources (optional)

- Place executable scripts in `scripts/`
- Place reference documentation in `references/`
- Place templates, images, or other output files in `assets/`

### Step 4: Test and iterate

Use the skill in real conversations, observe where the agent struggles, and refine the instructions accordingly.

## Example: Minimal Skill

```markdown
---
name: example
description: An example skill showing the SKILL.md format
---

# Example Skill

This is a sample skill that demonstrates the SKILL.md format.

## When to Use
Use this skill when the user asks for a greeting or wants to test the bot.

## Steps
1. Greet the user warmly
2. Ask how you can help

## Response Format
Keep responses friendly and concise.
```

## Example: Skill with Requirements

```markdown
---
name: deploy
description: Deploy the application to production
requires:
  env: [DEPLOY_TOKEN, AWS_REGION]
  bins: [docker, aws]
---

# Deploy

Use this skill to deploy the application to the production environment.

## Prerequisites
Ensure the Docker image is built and tagged before deploying.

## Steps
1. Build the Docker image
2. Push to the container registry
3. Update the ECS service
```

## Design Guidelines

- **Be concise.** The context window is shared with conversation history, other skills, and user requests. Only include information the agent does not already know.
- **Write clear descriptions.** The frontmatter `description` is the primary trigger for skill activation. Make it specific about what the skill does and when it should be used.
- **Use progressive disclosure.** Keep `SKILL.md` lean (metadata is always loaded, body only on activation, resources only as needed).
- **Match specificity to fragility.** Use detailed step-by-step instructions for fragile operations and high-level guidance for flexible tasks.
- **Avoid duplication.** Information should live in either `SKILL.md` or reference files, not both.
- **Do not include extraneous files.** Skills should contain only what the agent needs to do its job -- no READMEs, changelogs, or installation guides.
