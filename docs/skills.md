# Skills

Skills define what the OpenBotX agent knows and how it behaves in specific contexts. They are the primary mechanism for extending the agent with specialized knowledge, workflows, and domain expertise.

## Overview

A skill is a Markdown file with YAML frontmatter that provides instructions to the AI agent. Skills transform OpenBotX from a general-purpose assistant into a specialized agent equipped with procedural knowledge for specific domains or tasks.

Skills are loaded by the `SkillsLoader` class (`openbotx/agent/skills.py`) and injected into the system prompt by the `ContextBuilder` (`openbotx/agent/context.py`).

## Skill Locations

Skills live in three tiers, loaded in priority order:

1. **Built-in skills** -- `openbotx/skills/<skill-name>/` inside the OpenBotX package. Ship with the platform, always available. Lowest priority.
2. **Project skills** -- `<project_path>/skills/` in the project root (where `config.yml` lives). Shared across all agents. Overrides built-in.
3. **Agent workspace skills** -- `<workspace>/skills/` in each agent's workspace directory. Scoped to that agent only. Highest priority.

Both project and workspace skill directories support flat (`skills/<name>/SKILL.md`) and nested (`skills/<source>/<name>/SKILL.md`) layouts.

**Precedence rule:** The `SkillsLoader` scans all three tiers using the skill directory name as the key. A higher-tier skill with the same name replaces the lower-tier entry entirely: workspace overrides project, project overrides built-in.

**Agent visibility:** Each agent sees built-in + project + its own workspace skills. Project skills are shared across all agents. Workspace skills are private to the agent whose workspace they live in.

## Directory Structure

Each skill is a directory containing a required `SKILL.md` file and optional resource subdirectories:

```
skill-name/
├── SKILL.md              (required)
├── scripts/              (optional - executable code)
├── references/           (optional - documentation for context)
└── assets/               (optional - files used in output)
```

The directory name serves as the skill identifier. Use lowercase letters, digits, and hyphens only. Names must be under 64 characters.

For nested skills installed from the marketplace, the identifier includes the publisher prefix: `anthropic/pdf`, `community/web-scraper`. For flat skills, the identifier is just the directory name: `my-skill`. Two skills with the same name but different publishers (e.g., `anthropic/pdf` and `community/pdf`) are distinct and can coexist.

Project and workspace skill directories share the same layout:

```
project_root/
├── config.yml
├── skills/                        # project skills (shared by all agents)
│   ├── my-skill/                  # direct skill
│   │   └── SKILL.md
│   └── anthropic/                 # marketplace source
│       └── pdf/
│           └── SKILL.md
└── workspace/                     # agent "main" workspace
    └── skills/                    # workspace skills (private to this agent)
        ├── custom-tool/
        │   └── SKILL.md
        └── community/
            └── web-scraper/
                └── SKILL.md
```

## SKILL.md Format

Every `SKILL.md` file has two parts: YAML frontmatter and a Markdown body.

### Frontmatter Fields

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `name` | Yes | string | Skill identifier, used in the skills summary |
| `description` | Yes | string | What the skill does and when to use it. Primary triggering mechanism -- the agent reads this to decide whether to activate the skill |
| `always` | No | boolean | If `true`, the skill body is always included in the system prompt (default: `false`) |
| `requires` | No | object | Runtime requirements that must be satisfied for the skill to be available |

### Requirements

The `requires` field supports two types of checks:

- **`bins`** -- A list of binary names that must be available on `PATH` (checked via `shutil.which`).
- **`env`** -- A list of environment variable names that must be set (checked via `os.environ`).

Both accept either a single string or a list of strings. All listed requirements must be satisfied for the skill to report as `available`. If any requirement is missing, the skill appears in the summary with `status="unavailable"`.

```yaml
---
name: deploy
description: Deploy the application to production environments using Docker and AWS
requires:
  bins:
    - docker
    - aws
  env:
    - DEPLOY_TOKEN
    - AWS_REGION
---
```

### Writing Effective Descriptions

The `description` field is the most important part of the frontmatter. The agent reads all skill descriptions to decide which skills to activate, so a well-written description directly impacts triggering accuracy.

- Include **both** what the skill does and **when** to use it
- Be slightly broad in scope to avoid under-triggering -- include related phrases and contexts the user might use
- All "when to use" information goes in the description, not in the body (the body is only loaded after triggering)

**Weak description:**
```yaml
description: Process DOCX files
```

**Strong description:**
```yaml
description: Create, edit, and analyze documents (.docx). Use when working with professional documents including creating new documents, modifying content, tracked changes, comments, formatting, or text extraction.
```

### Body

The Markdown body contains the actual instructions for the agent. This content is loaded into context only when the skill is activated (or always, if `always: true`).

**Writing guidelines:**

- Use imperative form ("Extract the data", not "The data should be extracted")
- Keep under 500 lines to avoid context bloat
- Explain the reasoning behind important choices, not just rules
- Prefer concise examples over verbose explanations
- Start with the most common use case, then cover variations

## How Skills Are Loaded

The `SkillsLoader` manages the full lifecycle:

1. **Discovery** -- `_discover_skills()` scans all three tiers and builds a key-to-path mapping. Flat skills use the directory name as key (`my-skill`), nested skills use `publisher/name` (`anthropic/pdf`):
   - Built-in: `openbotx/skills/<name>/SKILL.md`
   - Project: `<project_path>/skills/<name>/SKILL.md` or `<project_path>/skills/<publisher>/<name>/SKILL.md`
   - Workspace: `<workspace>/skills/<name>/SKILL.md` or `<workspace>/skills/<publisher>/<name>/SKILL.md`

2. **Listing** -- `list_skills()` returns metadata for all discovered skills: `name` (the key, e.g., `anthropic/pdf`), `description`, `available`, `always`, `source` (`builtin`, `project`, or `workspace`), and `publisher` (extracted from the key, empty for flat skills). Results are sorted alphabetically by skill name. This metadata is formatted into an XML summary by `build_skills_summary()` and included in every system prompt so the agent knows what skills exist.

3. **Always-on loading** -- `get_always_skills()` returns the full body of skills marked with `always: true` (provided their requirements are met). These are injected directly into the system prompt by `ContextBuilder`.

4. **On-demand loading** -- `load_skill(name)` returns the body of a specific skill, stripped of frontmatter. This is used when the agent decides to activate a particular skill during a conversation.

### Skills Summary Format

The skills summary is injected into the system prompt as XML:

```xml
<available_skills>
  <skill always="true"><name>memory</name><description>Two-layer memory system with search-based recall.</description><location>/path/to/SKILL.md</location><status>available</status></skill>
  <skill><name>browser</name><description>Automate browser interactions...</description><location>/path/to/SKILL.md</location><status>available</status></skill>
  <skill><name>weather</name><description>Get current weather data...</description><location>/path/to/SKILL.md</location><status>unavailable</status></skill>
</available_skills>
```

### Per-Agent Loading

Each agent gets its own `SkillsLoader` instance, created during orchestrator startup. The loader is initialized with the project path and the agent's workspace path (`SkillsLoader(project_path, workspace)`), so it sees built-in + project + that agent's workspace skills. Both parameters are optional: omitting `workspace` returns only built-in + project skills.

Agents that share the same workspace directory share the same set of workspace skills. When listing all skills (no agent filter), workspace skills are deduplicated by workspace path -- the first agent name is used as the label.

### Skills API

The server exposes a REST API for managing skills:

- `GET /api/skills` -- List all skills. Supports an optional `agent` query parameter:
  - No parameter: returns all skills across all locations (project and each workspace shown independently)
  - `agent=`: returns built-in + project skills only
  - `agent=<name>`: returns built-in + project + that agent's workspace skills
- `GET /api/skills/<name>` -- Get a skill's raw content. Supports `?agent=` to target the correct location.
- `PUT /api/skills/<name>` -- Update a skill's SKILL.md. Supports `?agent=`.
- `DELETE /api/skills/<name>` -- Delete a skill directory. Supports `?agent=`.

For nested skills, the name includes the publisher prefix (e.g., `/api/skills/anthropic/pdf`).

Each skill in the list response includes: `name`, `description`, `always`, `source` (`builtin`/`project`/`workspace`), `publisher`, and `agent` (the agent name for workspace skills, empty otherwise).

## Bundled Resources

### Scripts (`scripts/`)

Executable code (Python/Bash/etc.) for tasks that require deterministic reliability or are repeatedly rewritten.

- Include when the same code would be rewritten repeatedly across invocations
- Token-efficient, deterministic, and can be executed without loading into context
- Scripts may still need to be read by the agent for patching or environment-specific adjustments

### References (`references/`)

Documentation loaded as needed to inform the agent's reasoning.

- Keeps SKILL.md lean -- move detailed schemas, API docs, and domain knowledge here
- For large files (>300 lines), include a table of contents at the top
- Reference clearly from SKILL.md with guidance on when to read each file
- Avoid duplication: information should live in either SKILL.md or references, not both

### Assets (`assets/`)

Files used in output, not intended to be loaded into context.

- Templates, images, icons, boilerplate code, fonts, sample documents
- The agent uses these files directly in its output without reading them into context

### What NOT to Include

A skill should only contain essential files. Do NOT create:

- README.md, INSTALLATION_GUIDE.md, QUICK_REFERENCE.md, CHANGELOG.md
- User-facing documentation, setup guides, or testing procedures

## Progressive Disclosure

Skills use a three-level loading system to manage context efficiently:

1. **Metadata** (name + description) -- always in context (~100 words)
2. **SKILL.md body** -- loaded when skill triggers (<500 lines)
3. **Bundled resources** -- loaded as needed by the agent (unlimited)

When SKILL.md approaches 500 lines, split content into reference files with clear pointers about when to read them.

### Pattern: High-Level Guide with References

```markdown
# PDF Processing

## Quick start
Extract text with pdfplumber:
[concise example]

## Advanced features
- **Form filling**: See references/forms.md for complete guide
- **API reference**: See references/api.md for all methods
```

The agent loads reference files only when needed.

### Pattern: Domain-Specific Organization

```
bigquery-skill/
├── SKILL.md (overview and navigation)
└── references/
    ├── finance.md (revenue, billing metrics)
    ├── sales.md (opportunities, pipeline)
    └── product.md (API usage, features)
```

When the user asks about sales, the agent only reads `sales.md`.

### Pattern: Conditional Details

```markdown
# DOCX Processing

## Creating documents
Use docx-js for new documents. See references/docx-js.md.

## Editing documents
For simple edits, modify the XML directly.
**For tracked changes**: See references/redlining.md
```

## Built-in Skills

OpenBotX ships with eleven built-in skills.

### browser

Automate browser interactions for web scraping, testing, and navigation. Controls Chrome browser via CDP (Chrome DevTools Protocol) to navigate pages, interact with elements, capture screenshots, and extract content.

- **Tool:** `browser`
- **Actions:** `navigate`, `snapshot`, `screenshot`, `click`, `type`, `press`, `inspect`, `evaluate`, `wait`
- **Requires:** `google-chrome` binary on PATH

### cron

Schedule reminders and recurring tasks. Supports three modes: reminders (message sent directly to user), tasks (agent executes and sends result), and one-time scheduled events that auto-delete after firing.

- **Tool:** `cron`
- **Actions:** `add`, `list`, `remove`
- **Always loaded:** Yes
- **Supports:** interval-based scheduling (`every_seconds`), cron expressions (`cron_expr`), one-time scheduling (`at`), and IANA timezone awareness (`tz`)

### http-client

Make HTTP requests (GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS) to APIs and web services. Handles JSON, form-encoded, and plain text bodies. Supports named auth profiles (OAuth 1.0a, Basic, Bearer), file download, and multipart upload.

- **Tool:** `http_client`
- **Parameters:** `method`, `url`, `headers`, `body`, `auth`, `download_path`, `upload_file`

### image-generation

Generate images from text descriptions using AI models. Provider-routed: Gemini models use the Google GenAI SDK with native support for aspect ratio, resolution, reference images, style hints, and Google Search grounding. Other models use litellm.

- **Tool:** `generate_image`
- **Parameters:** `prompt`, `filename`, `aspect_ratio`, `size`, `reference_images`, `style`, `negative_prompt`, `google_search`

### memory

### pillow

Manipulate images locally using Python and PIL/Pillow. Covers resizing, cropping, rotating, filtering, enhancing, compositing, watermarking, adding text, creating animated GIFs, and extracting metadata. Uses `write_file` + `exec` to run Pillow scripts.

- **Tools:** `write_file`, `exec`
- **Capabilities:** resize, crop, rotate, flip, filter, enhance, composite, watermark, text rendering, animated GIFs, format conversion, channel operations
- **Bundled resources:** `references/api.md` — complete module-by-module API reference

Two-layer memory system with search-based recall. Manages long-term facts in `memory/MEMORY.md` (always loaded into context) and an append-only event log in `memory/HISTORY.md` (searchable via `memory_search`).

- **Tools:** `memory_save`, `memory_read`, `memory_search`
- **Always loaded:** Yes
- **Auto-consolidation:** Old conversations are automatically summarized and appended to the history file

### rss-reader

Read RSS and Atom feeds and return the latest entries. Auto-detects feed format, strips HTML from summaries.

- **Tool:** `rss_reader`
- **Parameters:** `url`, `count`

### skill-creator

Create or update OpenBotX skills from within a conversation. Provides guidance on skill structure, frontmatter fields (including `always` and `requires`), naming conventions, progressive disclosure, bundled resources, description writing, and the full creation workflow from understanding through iteration.

### summarize

Summarize or extract text and transcripts from URLs, podcasts, YouTube videos, and local files. Uses the `summarize` CLI tool with configurable models and output lengths.

- **Requires:** `summarize` binary on PATH
- **Supports:** Multiple AI providers (OpenAI, Anthropic, Google, xAI), YouTube transcript extraction, Firecrawl fallback for blocked sites

### twitter

Post tweets on Twitter/X using the `http_client` tool with the `twitter` auth profile. Supports text tweets, media uploads, threads, and tweet deletion.

- **Tool:** `http_client` with `auth: "twitter"`
- **Requires:** `twitter` auth profile configured in `tools.http_client.auth_profiles`

### weather

Get current weather and forecasts using free services (no API key required). Uses wttr.in as the primary source and Open-Meteo as a JSON fallback.

- **Requires:** `curl` binary on PATH

## Context Files

In addition to skills, OpenBotX uses context files placed in the project root (where `config.yml` lives) to shape agent behavior. These are loaded by `ContextBuilder` and included in every system prompt:

| File | Purpose |
|------|---------|
| `SOUL.md` | Bot personality, tone, and behavioral guidelines |
| `USER.md` | User preferences and personalization information |
| `AGENTS.md` | Agent and subagent configuration and capabilities |
| `TOOLS.md` | Available tools documentation |

These files are optional. If present, their contents are included under a heading in the system prompt (e.g., `# SOUL.md`).

## Creating a New Skill

### Step 1: Capture Intent

Understand what the skill should do through concrete examples. Key questions:

- What should this skill enable the agent to do?
- When should this skill trigger? (what user phrases/contexts)
- What's the expected output format?
- Are there edge cases or constraints?

### Step 2: Plan Reusable Contents

Analyze each concrete example:

1. How would you execute this from scratch?
2. What scripts, references, or assets would help when repeating this?

If you find yourself writing the same helper code each time, extract it into a `scripts/` file.

### Step 3: Create the Directory

Place the skill in the project (shared) or a specific agent's workspace (private):

```
# shared across all agents
<project_root>/skills/my-skill/
├── SKILL.md
├── scripts/      (if needed)
├── references/   (if needed)
└── assets/       (if needed)

# private to one agent
<workspace>/skills/my-skill/
└── SKILL.md
```

Only create resource directories that are actually needed.

### Step 4: Write SKILL.md

```yaml
---
name: my-skill
description: >
  A clear description of what this skill does. Use when the user needs to
  [specific trigger], [another trigger], or [related context].
---
```

```markdown
# My Skill

Instructions for the agent when this skill is activated.

## Steps
1. First action
2. Second action

## Examples
[concise, practical examples]
```

### Step 5: Test and Iterate

Use the skill in real conversations, observe where the agent struggles, and refine:

1. Notice inefficiencies or incorrect behavior
2. Update SKILL.md or bundled resources
3. Look for repeated work -- if the agent keeps writing the same helper code, bundle it as a script
4. Test again

## Design Guidelines

- **Be concise.** The context window is shared with conversation history, other skills, and user requests. Only include information the agent does not already know. Prefer concise examples over verbose explanations.
- **Explain the why.** Explain reasoning behind important choices instead of rigid rules. The agent has good theory of mind -- clear reasoning is more effective than heavy-handed constraints.
- **Write clear descriptions.** The frontmatter `description` is the primary trigger for skill activation. Include both what the skill does and when it should be used. Be slightly broad to avoid under-triggering.
- **Use progressive disclosure.** Keep SKILL.md lean. Metadata is always loaded, body only on activation, resources only as needed. Split to reference files when approaching 500 lines.
- **Match specificity to fragility.** Use detailed step-by-step instructions for fragile operations and high-level guidance for flexible tasks.
- **Avoid duplication.** Information should live in either SKILL.md or reference files, not both.
- **No extraneous files.** Skills should contain only what the agent needs -- no READMEs, changelogs, or installation guides.
