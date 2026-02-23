# OpenBotX - Concepts and Architecture

This document explains the main concepts of OpenBotX and the practical purpose of each.

## Overview

OpenBotX implements several patterns to build a robust agent system:

1. **Tool Control** - Profiles and groups to manage tool access
2. **Message Directives** - Per-message behavior control
3. **Prompt Modes** - Token economy via modular prompts
4. **Skills with Precedence** - Skills system with sources and priorities
5. **Context Compaction** - Strategies to manage history
6. **Skill Eligibility** - System requirement verification

---

## 1. Tool Control System

### ToolProfile

Controls WHICH tools are available to the agent on each request.

**Why it exists**
- Security: Limit sensitive tools by context
- Performance: Fewer tools = fewer tokens in the prompt
- Context: Different tasks need different tool sets

**Values:**
| Profile | Available Tools | Typical Use |
|---------|-----------------|-------------|
| `minimal` | SYSTEM only | Simple conversations, no actions |
| `coding` | SYSTEM + FS + DATABASE | Programming tasks |
| `messaging` | SYSTEM + MESSAGING + WEB | Social interactions |
| `full` | All tools | Complex tasks (default) |

**How to use:**
```
User: /minimal what is the capital of France?
User: /coding create a file test.py
User: /full do backup and send by email
```

### ToolGroup

Categories tools into logical groups.

**Why it exists**
- Organization: Group related tools
- Flexibility: Enable/disable specific groups
- Mapping: Connect profiles to tool sets

**Available groups:**
| Group | Description |
|-------|-------------|
| `system` | Basic system operations |
| `fs` | File system |
| `web` | Web access/scraping |
| `memory` | Knowledge base |
| `sessions` | Session management |
| `ui` | UI interactions |
| `automation` | Task automation |
| `messaging` | Messaging operations |
| `database` | Database |
| `storage` | Storage |
| `scheduler` | Job scheduling |

---

## 2. Message Directives (MessageDirective)

Lets the user control agent behavior PER MESSAGE.

**Why it exists**
- Granular control: Each message can have different behavior
- Flexibility: User decides when more detail is needed
- Permissions: Temporary elevation for sensitive actions

**Available directives:**
| Directive | Effect |
|-----------|--------|
| `/think` | Enable extended thinking mode |
| `/verbose` | More detailed responses |
| `/reasoning` | Show reasoning process |
| `/elevated` | Request elevated permissions |

**How to use:**
```
User: /reasoning why does the code not work?
User: /elevated delete temporary files
User: /verbose explain how REST works
```

---

## 3. Prompt Modes (PromptMode)

Controls system prompt verbosity to save tokens.

**Why it exists**
- Economy: Smaller prompts = fewer tokens = lower cost
- Performance: Less context = faster responses
- Focus: Some tasks do not need all instructions

**Available modes:**
| Mode | Sections Included | Economy |
|------|-------------------|----------|
| `full` | All (identity, security, formatting, language, tools, skills, memory, reasoning) | None |
| `minimal` | Essentials only (identity, security, language) | ~60% tokens |
| `none` | None | ~90% tokens |

**How to activate:**
```
User: /quiet answer yes or no    # Uses MINIMAL
User: /silent 2+2                  # Uses NONE
```

**Section priority structure:**
```
100 - CONTEXT (date, time, locale)
 90 - IDENTITY (who the bot is)
 85 - SECURITY (security policies)
 80 - FORMATTING (formatting rules)
 75 - LANGUAGE (localization)
 60 - TOOLS (available tools)
 50 - SKILLS (active skills)
 48 - SKILL_USAGE (how to use skills)
 40 - MEMORY (history/summary)
 38 - MEMORY_CONTEXT (how to use memory)
 30 - REASONING (reasoning mode)
 20 - CUSTOM (custom instructions)
```

---

## 4. Skills System

### SkillSource

Defines the SOURCE of a skill and its load priority.

**Why it exists**
- Override: Workspace skills override bundled ones
- Organization: Separate built-in from custom skills
- Flexibility: User can customize existing skills

**Precedence order (higher = priority):**
| Source | Priority | Location |
|-------|----------|----------|
| `extra` | 0 | External skills |
| `bundled` | 1 | Inside openbotx package |
| `managed` | 2 | Managed (e.g. cloud) |
| `workspace` | 3 | Project ./skills directory |

**Behavior:**
If two skills have the same ID, the higher-priority one wins.
```
bundled/greeting/SKILL.md  (priority 1)
workspace/greeting/SKILL.md (priority 3) <- This one is used
```

### SkillEligibilityReason

Explains WHY a skill cannot be used.

**Why it exists**
- Debugging: Know why a skill does not appear
- Validation: Ensure only functional skills are loaded
- Feedback: Inform user about missing requirements

**Possible reasons:**
| Reason | Meaning | Example |
|--------|---------|---------|
| `os_incompatible` | Wrong OS | Skill requires macOS, user has Linux |
| `missing_binary` | Missing binary | Skill requires `ffmpeg`, not installed |
| `config_disabled` | Disabled in config | `skill.enabled: false` |
| `missing_provider` | Provider unavailable | Skill requires Telegram, not configured |

**In SKILL.md:**
```yaml
---
name: audio-transcribe
requires:
  os: [darwin, linux]
  binaries: [ffmpeg, whisper]
  providers: [transcription]
---
```

---

## 5. Context Compaction (CompactionStrategy)

Strategies to manage history when it exceeds the token limit.

**Why it exists**
- Context limit: LLMs have a token limit
- Cost: More tokens = higher cost
- Relevance: Keep important information, discard old

**Available strategies:**

### ADAPTIVE (default)
Dynamically adjusts based on available budget.
- Prioritizes recent messages
- Guarantees minimum message count
- Best for normal conversations

```
Budget: 50000 tokens
History: 80000 tokens
Result: Keeps last N messages that fit
```

### PROGRESSIVE
Progressively summarizes old messages.
- Keeps recent messages intact
- Creates/updates summary of older ones
- Best for long important conversations

```
Budget: 50000 tokens
History: 80000 tokens
Result: Summary of older + last N messages
```

### TRUNCATE
Simply removes old messages.
- Simplest and fastest
- Loses old context
- Use when history does not matter

```
Budget: 50000 tokens
History: 80000 tokens
Result: Remove until it fits the budget
```

---

## 6. Dual Summary System

Keeps two separate summaries for better context.

**Why it exists**
- Personalization: Remember who the user is
- Context: Know what is being discussed
- Economy: Summaries are smaller than full history

**Structure:**
| Summary | Content | Example |
|---------|----------|---------|
| `user_summary` | User profile | "User is a Python developer, prefers direct answers" |
| `conversation_summary` | Conversation context | "Discussing REST API implementation with JWT auth" |

**In the prompt:**
```
## Conversation Memory

USER PROFILE:
User is a Python developer, prefers direct answers

CONVERSATION CONTEXT:
Discussing REST API implementation with JWT auth

RECENT MESSAGES:
[USER]: how do I add rate limiting?
[ASSISTANT]: you can use slowapi...
```

---

## Processing Flow

```
1. Message arrives via Gateway
   |
2. Parse directives (/think, /minimal, etc)
   |
3. Resolve ToolProfile and filter tools
   |
4. Load channel context
   |
5. Apply CompactionStrategy if needed
   |
6. Build prompt with appropriate PromptMode
   |
7. Inject relevant skills (full content)
   |
8. Process with AgentBrain
   |
9. Save to context
   |
10. Trigger summarization if needed (background)
   |
11. Send response via Gateway
```

---

## Configuration

### Directives via message
```
/minimal /quiet simple question
/full /verbose /reasoning explain in detail
/elevated perform sensitive action
```

### Skills (SKILL.md)
```yaml
---
name: my-skill
description: What it does
triggers:
  keywords: [word1, word2]
requires:
  os: [darwin, linux]
  binaries: [ffmpeg]
  providers: [storage]
security:
  approval_required: true
---

# Skill Content

Detailed instructions that will be injected into the prompt...
```

### Tool definition
```python
@dataclass
class ToolDefinition:
    name: str
    description: str
    group: ToolGroup = ToolGroup.SYSTEM
    requires_approval: bool = False
```

---

## 7. Background Services

**What it is**

Background services are processes that start when the application starts and stop when it shuts down. They run in the background (non-blocking) and follow the same start/stop pattern as gateways and providers.

**Why it exists**

- **Single lifecycle**: Start and stop are centralized in one place (`start_background_services`, `stop_background_services`).
- **Non-blocking**: Services run as asyncio tasks so the main application (API or CLI) is not blocked.
- **Extensibility**: New services (e.g. metrics, health probes) can be added by registering them in the background loader.

**Current services**

| Service | Config key | Description |
|--------|------------|-------------|
| **relay** | `relay.enabled`, `relay.host`, `relay.port` | Browser relay for the Chrome extension (see below). |

**Flow**

1. On startup (API or CLI), `start_background_services(config)` is called.
2. For each registered service, if `enabled(config)` is true, its start coroutine is run as `asyncio.create_task(...)`.
3. On shutdown, `stop_background_services()` cancels all tasks and awaits cleanup.

**Configuration (e.g. relay)**

```yaml
relay:
  enabled: false
  host: "127.0.0.1"
  port: 18792
```

---

## 8. Browser Relay (Chrome Extension)

**What it is**

The relay is an HTTP + WebSocket server that bridges the OpenBotX CDP client (`cdp_tool`) and a Chrome extension. The extension attaches to Chrome tabs via `chrome.debugger` and forwards CDP messages to the relay; the relay exposes the same HTTP/WS surface as a normal Chrome remote-debugging endpoint so CDP clients can connect.

**Why it exists**

- **Use existing Chrome**: The user can drive their normal Chrome window (or a dedicated profile) without needing to launch a separate browser.
- **Same machine**: Relay and extension run on the machine where Chrome runs; OpenBotX can run elsewhere and connect to the relay.

**Components**

| Component | Role |
|----------|------|
| **Relay server** | Listens on `relay.host:relay.port`. Serves `/`, `/json/version`, `/json/list`, WebSocket `/extension` (extension) and `/cdp` (CDP clients). |
| **Chrome extension** | Connects to `ws://relay.host:relay.port/extension`, attaches to tabs via `chrome.debugger`, executes CDP commands and forwards events. |
| **CDP tools** | Connect to `http://relay.host:relay.port` (uses `/json/version` then `ws://.../cdp`). |

**When relay is enabled**

- Relay starts automatically with OpenBotX (API or CLI) as a background service.
- User sets the same port in the extension options, then clicks the toolbar button to attach a tab.
- Tools like `cdp_navigate`, `cdp_snapshot`, `cdp_tabs` use the attached tab(s).

---

## 9. CDP Tools

**What it is**

OpenBotX provides CDP tools (`cdp_*`) to automate browsers via Chrome DevTools Protocol:

- **CDP tools** (`cdp_*`): Connect to an existing browser (Chrome with remote debugging or the relay). They control the attached tab(s) without launching a new browser.

**How it works**

- **Default for browser automation**: When the user asks to open a URL, navigate, or read a page, the agent uses CDP tools to control the user's existing Chrome (or relay-attached tab).
- Tool **descriptions** guide the model to use CDP tools for site access and browser automation.
