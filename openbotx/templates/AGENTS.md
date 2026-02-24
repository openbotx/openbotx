# Agents

Configuration for agent behavior and subagent capabilities.

## Main Agent
The main agent handles user conversations, uses tools, and can spawn subagents for background tasks.

## Subagents
Subagents are spawned for independent tasks that can run in parallel. They have access to:
- File system tools (read, write, edit, list)
- Shell execution
- Web search and fetch
- HTTP client

Subagents do NOT have access to:
- Message tool (cannot message the user directly)
- Spawn tool (cannot create other subagents)
- Cron tool (cannot schedule tasks)
