---
name: memory
description: Two-layer memory system with search-based recall. Use to save important facts, search past events, or recall user preferences and project context across conversations.
always: true
---

# Memory

## Structure

- `memory/MEMORY.md` -- Long-term facts (preferences, project context, relationships). Always loaded into your context.
- `memory/HISTORY.md` -- Append-only event log. NOT loaded into context. Search it with `memory_search`.

## Search Past Events

Use `memory_search` to find information across both memory files:

```
memory_search(query="keyword")
```

Returns matching lines with surrounding context, indicating which file each match came from.

## Read Memory Files

Use `memory_read` to read a full memory file:

```
memory_read(file="memory")
memory_read(file="history")
memory_read(file="history", max_lines=50)
```

Use `max_lines` to read only the most recent entries from HISTORY.md.

## When to Update MEMORY.md

Write important facts immediately using `memory_save`:
- User preferences ("I prefer dark mode")
- Project context ("The API uses OAuth2")
- Relationships ("Alice is the project lead")

## Auto-consolidation

Old conversations are automatically summarized and appended to HISTORY.md when the session grows large. Long-term facts are extracted to MEMORY.md. You don't need to manage this.
