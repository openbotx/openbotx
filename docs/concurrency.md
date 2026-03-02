# Concurrency

OpenBotX processes messages concurrently using a lane-based command queue.
Different chat sessions run in parallel; messages within the same session
are serialized to preserve ordering.

## Architecture

```
InboundMessage ─► Orchestrator.run() ─► CommandQueue.enqueue(lane, coro)
                      │                        │
                      │                   ┌────┴────┐
                      │                   │  Lanes  │
                      │                   ├─────────┤
                      │                   │ web:abc ─► process_message(msg1)
                      │                   │ web:def ─► process_message(msg2)  (parallel)
                      │                   │ web:abc ─► process_message(msg3)  (queued, same lane)
                      │                   │ cron:x  ─► process_message(msg4)  (parallel)
                      │                   └─────────┘
                      │                        │
                      │                   Global semaphore (max_concurrent)
                      ▼
              AgentLoop.process_message()
                      │
              RequestContext(channel, chat_id, task_id, agent_name)
                      │
              ToolRegistry.execute(name, params, context=ctx)
                      │
              Tool.execute(**params, _context=ctx)
```

### CommandQueue (`openbotx/bus/command_queue.py`)

Each lane is identified by a string key (typically `session_key` = `channel:chat_id`).
A lane has its own FIFO queue and a configurable concurrency limit (default 1 per lane).
A global `asyncio.Semaphore` caps the total number of parallel tasks across all lanes.

- `enqueue(lane, coro)` — add a coroutine to the lane, returns awaitable result
- `enqueue_nowait(lane, coro)` — fire-and-forget variant
- `drain()` — wait for all active tasks to finish (used during shutdown)
- `set_lane_concurrency(lane, n)` — override max concurrency for a specific lane

### Orchestrator

The orchestrator loop consumes messages from the bus and dispatches them
to the command queue. It no longer blocks on `process_message`; instead it
calls `enqueue_nowait(msg.session_key, coro)` and immediately returns to
consume the next message.

### RequestContext (`openbotx/tools/context.py`)

An immutable dataclass that carries per-request metadata:

```python
@dataclass(frozen=True)
class RequestContext:
    channel: str
    chat_id: str
    task_id: str
    agent_name: str
    message_id: str | None
```

Created once per `process_message` call and passed through the registry
to each tool execution via `kwargs["_context"]`. This replaces the
previous `set_context()` pattern where tools stored mutable state on
shared instances — which was unsafe for concurrent execution.

## Configuration

In `config.yaml`, under any agent's `agent_params`:

```yaml
agents:
  main:
    agent_params:
      max_concurrent: 1   # max parallel message processing across all lanes
```

The default is `1`. This value is read from the default agent and passed
to the orchestrator's `CommandQueue`.

## How Tools Use Context

Tools that need request-scoped data (channel, chat_id, etc.) read it from
`kwargs.get("_context")` in their `execute()` method:

```python
async def execute(self, content: str, **kwargs):
    ctx: RequestContext | None = kwargs.get("_context")
    channel = ctx.channel if ctx else ""
```

This pattern is used by `MessageTool`, `SpawnTool`, and `CronTool`.
Other tools (filesystem, web search, etc.) ignore the context.

## Guarantees

- Messages to the **same session** are processed in FIFO order (1 at a time per lane)
- Messages to **different sessions** run in parallel (up to `max_concurrent` total)
- Tool context is **isolated per request** — no shared mutable state between concurrent messages
- Graceful shutdown: `orchestrator.stop()` drains all active tasks before exiting
