---
name: skill-creator
description: Create or update OpenBotX skills. Use when users want to create a new skill, modify an existing one, or need guidance on skill structure, frontmatter, bundled resources, or best practices. Also use when the user says "turn this into a skill" or wants to capture a workflow as a reusable skill.
---

# Skill Creator

Guide for creating effective OpenBotX skills.

## About Skills

Skills are modular, self-contained packages that extend the agent's capabilities with specialized knowledge, workflows, and tools. They transform the agent from a general-purpose assistant into a specialized one equipped with procedural knowledge no model fully possesses.

**What skills provide:**

1. Specialized workflows - multi-step procedures for specific domains
2. Tool integrations - instructions for working with specific file formats or APIs
3. Domain expertise - company-specific knowledge, schemas, business logic
4. Bundled resources - scripts, references, and assets for complex and repetitive tasks

## Skill Locations

- **Builtin skills**: `openbotx/skills/<skill-name>/SKILL.md` — shipped with the project, read-only
- **Project skills**: `<workspace>/skills/<skill-name>/SKILL.md` — user-created, editable
- **Marketplace skills**: `<workspace>/skills/<source>/<skill-name>/SKILL.md` — installed from marketplace

When creating a new skill, always place it under `<workspace>/skills/`.

## Anatomy of a Skill

```
skill-name/
├── SKILL.md           (required)
│   ├── YAML frontmatter (required)
│   └── Markdown body    (required)
└── Bundled Resources    (optional)
    ├── scripts/         - executable code (Python/Bash/etc.)
    ├── references/      - documentation loaded into context as needed
    └── assets/          - files used in output (templates, icons, fonts)
```

### SKILL.md Frontmatter

The frontmatter is the primary mechanism for skill discovery and triggering.

```yaml
---
name: skill-name                # required - identifier
description: What it does...    # required - triggers skill selection
always: true                    # optional - always loaded into context (default: false)
requires:                       # optional - prerequisites
  bins:                         # optional - required binaries on PATH
    - some-binary
  env:                          # optional - required environment variables
    - SOME_API_KEY
---
```

**Fields:**

- `name` — skill identifier, shown in the skills list
- `description` — the primary triggering mechanism. The agent reads this to decide when to use the skill. Include both what the skill does AND when to use it. All "when to use" info must go here, not in the body (the body is only loaded after triggering)
- `always` — when `true`, the skill body is always loaded into the agent's context regardless of triggering. Use sparingly — only for skills that must always be active (e.g., memory, cron)
- `requires.bins` — list of binary names that must exist on PATH (checked via `shutil.which`). If any is missing, the skill is marked unavailable
- `requires.env` — list of environment variable names that must be set. If any is empty/unset, the skill is marked unavailable

### SKILL.md Body

Markdown instructions loaded only after the skill triggers. Use imperative form ("Extract the data", not "You should extract the data"). Keep under 500 lines.

### Bundled Resources

#### Scripts (`scripts/`)

Executable code for tasks that require deterministic reliability or are repeatedly rewritten.

- include when the same code would be rewritten repeatedly across invocations
- scripts are token-efficient, deterministic, and can be executed without loading into context
- **signal to bundle a script**: if you find yourself writing the same helper code every time the skill runs, extract it into a script

#### References (`references/`)

Documentation loaded as needed to inform the agent's reasoning.

- keeps SKILL.md lean — move detailed schemas, API docs, and domain knowledge here
- for large files (>300 lines), include a table of contents at the top
- reference clearly from SKILL.md with guidance on when to read each file
- avoid duplication: information should live in either SKILL.md or references, not both

#### Assets (`assets/`)

Files used in output, not intended to be loaded into context.

- templates, images, icons, boilerplate code, fonts, sample documents
- the agent uses these files directly in its output without reading them into context

### What NOT to Include

Only essential files. Do NOT create:

- README.md, INSTALLATION_GUIDE.md, QUICK_REFERENCE.md, CHANGELOG.md
- user-facing documentation, setup guides, or testing procedures

## Core Principles

### Concise is Key

The context window is shared. Skills compete for space with the system prompt, conversation history, other skills' metadata, and the user's request.

**The agent is already very smart.** Only add context it doesn't already have. Challenge each piece: "Does the agent really need this?" and "Does this paragraph justify its token cost?"

Prefer concise examples over verbose explanations.

### Explain the Why

Explain **why** things are important instead of heavy-handed constraints. The agent has good theory of mind — when given clear reasoning, it can go beyond rote instructions. If you find yourself writing ALWAYS or NEVER in all caps, reframe and explain the reasoning instead. That's more effective than rigid rules.

### Set Appropriate Degrees of Freedom

Match specificity to the task's fragility:

- **High freedom** (text instructions) — multiple approaches are valid, decisions depend on context
- **Medium freedom** (pseudocode/scripts with parameters) — a preferred pattern exists, some variation is acceptable
- **Low freedom** (specific scripts, few parameters) — operations are fragile, consistency is critical

Think of the agent exploring a path: a narrow bridge with cliffs needs guardrails, an open field allows many routes.

### Progressive Disclosure

Skills use a three-level loading system:

1. **Metadata** (name + description) — always in context (~100 words)
2. **SKILL.md body** — loaded when skill triggers (<500 lines)
3. **Bundled resources** — loaded as needed by the agent (unlimited)

When SKILL.md approaches 500 lines, split content into reference files with clear pointers about when to read them.

**Pattern: high-level guide with references**

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

**Pattern: domain-specific organization**

```
bigquery-skill/
├── SKILL.md (overview and navigation)
└── references/
    ├── finance.md (revenue, billing metrics)
    ├── sales.md (opportunities, pipeline)
    └── product.md (API usage, features)
```

When the user asks about sales, the agent only reads `sales.md`.

**Pattern: conditional details**

```markdown
# DOCX Processing

## Creating documents
Use docx-js for new documents. See references/docx-js.md.

## Editing documents
For simple edits, modify the XML directly.
**For tracked changes**: See references/redlining.md
```

## Skill Creation Process

### Step 1: Capture Intent

Understand the skill's purpose through concrete examples. If the current conversation already contains a workflow the user wants to capture, extract answers from the history first — the tools used, the sequence of steps, corrections made, input/output formats observed.

Key questions to resolve:

1. What should this skill enable the agent to do?
2. When should this skill trigger? (what user phrases/contexts)
3. What's the expected output format?
4. Are there edge cases or constraints?

Don't ask too many questions at once. Start with the most important and follow up as needed.

### Step 2: Plan Reusable Contents

Analyze each concrete example:

1. How would you execute this from scratch?
2. What scripts, references, or assets would help when repeating this?

**Examples:**

- Building a `pdf-editor` skill for "rotate this PDF" → a `scripts/rotate_pdf.py` avoids rewriting the same code each time
- Building a `webapp-builder` skill for "build me a todo app" → an `assets/template/` with boilerplate project files
- Building a `bigquery` skill for "how many users logged in today?" → a `references/schema.md` documenting table schemas

### Step 3: Create the Skill

Create the skill directory under `<workspace>/skills/`:

```
<workspace>/skills/skill-name/
├── SKILL.md
├── scripts/      (if needed)
├── references/   (if needed)
└── assets/       (if needed)
```

Only create resource directories that are actually needed.

### Step 4: Write the SKILL.md

#### Frontmatter

Write a clear `name` and comprehensive `description`:

- `description` is the primary triggering mechanism — include both what the skill does AND specific triggers/contexts
- make descriptions slightly "broad" in scope to avoid under-triggering — include related phrases and contexts the user might use even if they don't explicitly name the skill
- example: instead of "Process DOCX files", write "Create, edit, and analyze documents (.docx). Use when working with professional documents: creating new documents, modifying content, tracked changes, comments, formatting, or text extraction"

Only add `always`, `requires.bins`, or `requires.env` when actually needed.

#### Body

Write instructions for using the skill and its bundled resources. Guidelines:

- use imperative form ("Extract the data", not "The data should be extracted")
- explain the reasoning behind important choices, not just the rules
- prefer concise examples over verbose explanations
- start with the most common use case, then cover variations
- reference bundled resources with guidance on when to read them
- keep under 500 lines — split to references if approaching this limit

### Step 5: Iterate

After using the skill on real tasks:

1. Notice struggles or inefficiencies
2. Identify what to update in SKILL.md or bundled resources
3. Look for repeated work across invocations — if the agent keeps writing the same helper code, bundle it as a script
4. Implement changes and test again

### Skill Naming

- lowercase letters, digits, and hyphens only
- normalize user titles to hyphen-case (e.g., "Plan Mode" → `plan-mode`)
- under 64 characters
- prefer short, verb-led phrases that describe the action
- name the folder exactly after the skill name
