import logging
from typing import Any

from openbotx.providers.base import LLMProvider

logger = logging.getLogger(__name__)

COMPACT_RATIO = 0.4  # summarize oldest 40% of conversation
MAX_TOOL_RESULT_IN_SUMMARY = 2000  # truncate tool results before summarizing

SUMMARY_PROMPT = (
    "Summarize the conversation below into a concise recap. Preserve:\n"
    "- Key decisions and conclusions\n"
    "- File paths, variable names, identifiers, URLs\n"
    "- Errors encountered and how they were resolved\n"
    "- Current task context and progress\n"
    "- User preferences and requirements\n\n"
    "Be concise but do not omit important technical details. "
    "Write the summary as a single block of text, not a conversation."
)


def _strip_for_summary(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Strip tool results and reasoning for compact summarization input."""
    stripped: list[dict[str, Any]] = []
    for msg in messages:
        clean = dict(msg)

        # truncate tool results
        if clean.get("role") == "tool":
            content = clean.get("content", "")
            if isinstance(content, str) and len(content) > MAX_TOOL_RESULT_IN_SUMMARY:
                tool_name = clean.get("name", "tool")
                clean["content"] = (
                    content[:MAX_TOOL_RESULT_IN_SUMMARY] + f"\n[{tool_name} output truncated]"
                )

        # remove reasoning content
        clean.pop("reasoning_content", None)

        stripped.append(clean)
    return stripped


async def compact_messages(
    messages: list[dict[str, Any]],
    provider: LLMProvider,
    model: str,
    model_params: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Summarize the oldest portion of conversation to reduce context size."""
    # separate system messages from conversation
    system_msgs = [m for m in messages if m.get("role") == "system"]
    conversation = [m for m in messages if m.get("role") != "system"]

    cut_point = max(2, int(len(conversation) * COMPACT_RATIO))
    if cut_point >= len(conversation):
        # nothing to compact, keep as-is
        return messages

    to_summarize = conversation[:cut_point]
    to_keep = conversation[cut_point:]

    # ensure to_keep starts with a valid message (not a dangling tool result)
    while to_keep and to_keep[0].get("role") == "tool":
        to_summarize.append(to_keep.pop(0))

    if not to_summarize:
        return messages

    try:
        summary = await _generate_summary(to_summarize, provider, model, model_params)
    except Exception as e:
        logger.error("compaction failed, keeping original messages: %s", e)
        return messages

    logger.info(
        "compacted %d messages into summary (%d chars), keeping %d recent",
        len(to_summarize),
        len(summary),
        len(to_keep),
    )

    compacted = (
        system_msgs
        + [
            {"role": "user", "content": f"[Previous conversation summary]:\n{summary}"},
            {
                "role": "assistant",
                "content": "Understood. I have the context from our previous conversation. How can I help you next?",
            },
        ]
        + to_keep
    )

    return compacted


async def _generate_summary(
    messages: list[dict[str, Any]],
    provider: LLMProvider,
    model: str,
    model_params: dict[str, Any] | None = None,
) -> str:
    """Use the LLM to generate a summary of the given messages."""
    stripped = _strip_for_summary(messages)

    # build a flat text representation for summarization
    parts: list[str] = []
    for msg in stripped:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if isinstance(content, list):
            text_parts = [p.get("text", "") for p in content if isinstance(p, dict)]
            content = " ".join(text_parts)
        if content:
            parts.append(f"[{role}]: {content}")

    conversation_text = "\n\n".join(parts)

    summary_messages = [
        {"role": "system", "content": SUMMARY_PROMPT},
        {"role": "user", "content": conversation_text},
    ]

    response = await provider.chat(
        messages=summary_messages,
        model=model,
        model_params=model_params,
    )

    return response.content or "[summary unavailable]"
