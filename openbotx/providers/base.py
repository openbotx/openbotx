from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCallRequest:
    """A tool call request from the LLM."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    """Response from an LLM provider."""

    content: str | None
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: dict[str, int] = field(default_factory=dict)
    reasoning_content: str | None = None
    error_type: str | None = None

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


@dataclass
class StreamChunk:
    """A single chunk from a streaming LLM response."""

    type: str  # "content", "tool_call", "reasoning", "usage", "done"
    content: str = ""
    tool_call_index: int = 0
    tool_call_id: str = ""
    tool_call_name: str = ""
    tool_call_arguments: str = ""
    usage: dict[str, int] = field(default_factory=dict)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, api_key: str | None = None, api_base: str | None = None):
        self.api_key = api_key
        self.api_base = api_base

    @staticmethod
    def _sanitize_empty_content(
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Replace empty text content that causes provider 400 errors."""
        result: list[dict[str, Any]] = []
        for msg in messages:
            content = msg.get("content")

            if isinstance(content, str) and not content:
                clean = dict(msg)
                clean["content"] = (
                    None
                    if (msg.get("role") == "assistant" and msg.get("tool_calls"))
                    else "(empty)"
                )
                result.append(clean)
                continue

            if isinstance(content, list):
                filtered = [
                    item
                    for item in content
                    if not (
                        isinstance(item, dict)
                        and item.get("type") in ("text", "input_text", "output_text")
                        and not item.get("text")
                    )
                ]
                if len(filtered) != len(content):
                    clean = dict(msg)
                    if filtered:
                        clean["content"] = filtered
                    elif msg.get("role") == "assistant" and msg.get("tool_calls"):
                        clean["content"] = None
                    else:
                        clean["content"] = "(empty)"
                    result.append(clean)
                    continue

            result.append(msg)
        return result

    @staticmethod
    def _convert_image_blocks(
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Convert internal image format to OpenAI-compatible format."""
        result: list[dict[str, Any]] = []
        for msg in messages:
            content = msg.get("content")
            if not isinstance(content, list):
                result.append(msg)
                continue
            converted = []
            for part in content:
                if (
                    isinstance(part, dict)
                    and part.get("type") == "image"
                    and "url" in part
                ):
                    converted.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": part["url"]},
                        }
                    )
                else:
                    converted.append(part)
            result.append({**msg, "content": converted})
        return result

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        model_params: dict[str, Any] | None = None,
    ) -> LLMResponse: ...

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        model_params: dict[str, Any] | None = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Stream an LLM response. Default falls back to non-streaming chat."""
        response = await self.chat(messages, tools, model, model_params)
        if response.content:
            yield StreamChunk(type="content", content=response.content)
        if response.usage:
            yield StreamChunk(type="usage", usage=response.usage)
        yield StreamChunk(type="done")

    @abstractmethod
    def get_default_model(self) -> str: ...
