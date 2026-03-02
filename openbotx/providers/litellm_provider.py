import os
import re
from typing import Any
from uuid import uuid4

import json_repair
import litellm
from litellm import acompletion

from openbotx.providers.base import LLMProvider, LLMResponse, ToolCallRequest
from openbotx.providers.registry import find_by_model, find_gateway

_ALLOWED_MSG_KEYS = frozenset({"role", "content", "tool_calls", "tool_call_id", "name"})


class LiteLLMProvider(LLMProvider):
    """LLM provider using LiteLLM for multi-provider support."""

    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        default_model: str = "",
        extra_headers: dict[str, str] | None = None,
        provider_name: str | None = None,
    ):
        super().__init__(api_key, api_base)
        self.default_model = default_model
        self.extra_headers = extra_headers or {}
        self._gateway = find_gateway(provider_name, api_key, api_base)

        if api_key:
            self._setup_env(api_key, api_base, default_model)

        if api_base:
            litellm.api_base = api_base

        litellm.suppress_debug_info = True
        litellm.drop_params = True

    def _setup_env(self, api_key: str, api_base: str | None, model: str) -> None:
        spec = self._gateway or find_by_model(model)
        if not spec or not spec.env_key:
            return

        if self._gateway:
            os.environ[spec.env_key] = api_key
        else:
            os.environ.setdefault(spec.env_key, api_key)

        effective_base = api_base or spec.default_api_base
        for env_name, env_val in spec.env_extras:
            resolved = env_val.replace("{api_key}", api_key)
            resolved = resolved.replace("{api_base}", effective_base)
            os.environ.setdefault(env_name, resolved)

    def _resolve_model(self, model: str) -> str:
        if self._gateway:
            prefix = self._gateway.litellm_prefix
            if self._gateway.strip_model_prefix:
                model = model.split("/")[-1]
            if prefix and not model.startswith(f"{prefix}/"):
                model = f"{prefix}/{model}"
            return model

        spec = find_by_model(model)
        if spec and spec.litellm_prefix:
            model = self._canonicalize_explicit_prefix(model, spec.name, spec.litellm_prefix)
            if not any(model.startswith(s) for s in spec.skip_prefixes):
                model = f"{spec.litellm_prefix}/{model}"

        return model

    @staticmethod
    def _canonicalize_explicit_prefix(model: str, spec_name: str, canonical_prefix: str) -> str:
        if "/" not in model:
            return model
        prefix, remainder = model.split("/", 1)
        if prefix.lower().replace("-", "_") != spec_name:
            return model
        return f"{canonical_prefix}/{remainder}"

    def _supports_cache_control(self, model: str) -> bool:
        if self._gateway is not None:
            return self._gateway.supports_prompt_caching
        spec = find_by_model(model)
        return spec is not None and spec.supports_prompt_caching

    def _apply_cache_control(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]] | None]:
        new_messages = []
        for msg in messages:
            if msg.get("role") == "system":
                content = msg["content"]
                if isinstance(content, str):
                    new_content = [
                        {
                            "type": "text",
                            "text": content,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ]
                else:
                    new_content = list(content)
                    new_content[-1] = {
                        **new_content[-1],
                        "cache_control": {"type": "ephemeral"},
                    }
                new_messages.append({**msg, "content": new_content})
            else:
                new_messages.append(msg)

        new_tools = tools
        if tools:
            new_tools = list(tools)
            new_tools[-1] = {**new_tools[-1], "cache_control": {"type": "ephemeral"}}

        return new_messages, new_tools

    def _apply_model_overrides(self, model: str, kwargs: dict[str, Any]) -> None:
        model_lower = model.lower()
        spec = find_by_model(model)
        if spec:
            for pattern, overrides in spec.model_overrides:
                if pattern in model_lower:
                    kwargs.update(overrides)
                    return

    @staticmethod
    def _sanitize_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        sanitized = []
        for msg in messages:
            clean = {k: v for k, v in msg.items() if k in _ALLOWED_MSG_KEYS}
            if clean.get("role") == "assistant" and "content" not in clean:
                clean["content"] = None
            sanitized.append(clean)
        return sanitized

    @staticmethod
    def _validate_transcript(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Ensure message ordering is valid for LLM APIs.

        Merges consecutive same-role messages, drops orphaned tool results,
        and guarantees tool messages follow an assistant message with tool_calls.
        """
        if not messages:
            return messages

        validated: list[dict[str, Any]] = []

        for msg in messages:
            role = msg.get("role")

            # system messages pass through unchanged
            if role == "system":
                validated.append(msg)
                continue

            # tool messages must follow an assistant message with tool_calls
            if role == "tool":
                last_non_tool = None
                for prev in reversed(validated):
                    if prev.get("role") != "tool":
                        last_non_tool = prev
                        break
                if (
                    last_non_tool
                    and last_non_tool.get("role") == "assistant"
                    and last_non_tool.get("tool_calls")
                ):
                    validated.append(msg)
                # orphaned tool result — drop it
                continue

            # merge consecutive user messages
            if role == "user":
                if validated and validated[-1].get("role") == "user":
                    prev_content = validated[-1].get("content", "")
                    cur_content = msg.get("content", "")
                    if isinstance(prev_content, str) and isinstance(cur_content, str):
                        validated[-1] = {
                            **validated[-1],
                            "content": f"{prev_content}\n\n{cur_content}",
                        }
                    else:
                        validated.append(msg)
                else:
                    validated.append(msg)
                continue

            # merge consecutive assistant messages (only when neither has tool_calls)
            if role == "assistant":
                if (
                    validated
                    and validated[-1].get("role") == "assistant"
                    and not validated[-1].get("tool_calls")
                    and not msg.get("tool_calls")
                ):
                    prev_content = validated[-1].get("content", "") or ""
                    cur_content = msg.get("content", "") or ""
                    validated[-1] = {
                        **validated[-1],
                        "content": f"{prev_content}\n\n{cur_content}".strip(),
                    }
                else:
                    validated.append(msg)
                continue

            validated.append(msg)

        return validated

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        model_params: dict[str, Any] | None = None,
    ) -> LLMResponse:
        original_model, kwargs = self._build_kwargs(messages, tools, model, model_params)
        if not original_model:
            return LLMResponse(
                content="No model configured. Set the 'model' field in your agent config (e.g. model: \"anthropic/claude-sonnet-4-20250514\").",
                finish_reason="error",
            )

        try:
            from openbotx.providers.retry import retry_with_backoff

            response = await retry_with_backoff(lambda: acompletion(**kwargs))
            return self._parse_response(response)
        except Exception as e:
            from openbotx.providers.errors import (
                ContextOverflowError,
                LLMErrorType,
                classify_error,
            )

            error_type = classify_error(e)
            # context overflow must propagate so the agent loop can compact
            if error_type == LLMErrorType.CONTEXT_OVERFLOW:
                raise ContextOverflowError(str(e)) from e
            safe_msg = self._sanitize_error_message(e)
            return LLMResponse(
                content=f"Error calling LLM: {safe_msg}",
                finish_reason="error",
                error_type=error_type.value,
            )

    @staticmethod
    def _sanitize_error_message(error: Exception) -> str:
        """Remove API keys and tokens from error messages."""
        msg = str(error)
        msg = re.sub(r"sk-[a-zA-Z0-9]{10,}", "[REDACTED]", msg)
        msg = re.sub(r"key-[a-zA-Z0-9]{10,}", "[REDACTED]", msg)
        msg = re.sub(r"Bearer\s+[a-zA-Z0-9_\-\.]{10,}", "Bearer [REDACTED]", msg)
        msg = re.sub(
            r"(api[_-]?key|token|secret|authorization)\s*[=:]\s*['\"]?[^\s,;'\"]{10,}",
            r"\1=[REDACTED]",
            msg,
            flags=re.IGNORECASE,
        )
        return msg

    @staticmethod
    def _sanitize_tool_call_id(tc_id: str | None) -> str:
        """Ensure tool call IDs are safe across providers."""
        if not tc_id or not tc_id.strip():
            return f"call_{uuid4().hex[:12]}"
        sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", tc_id)
        return sanitized or f"call_{uuid4().hex[:12]}"

    def _parse_response(self, response: Any) -> LLMResponse:
        choice = response.choices[0]
        message = choice.message

        tool_calls = []
        if hasattr(message, "tool_calls") and message.tool_calls:
            for tc in message.tool_calls:
                args = tc.function.arguments
                if isinstance(args, str):
                    args = json_repair.loads(args)
                tool_calls.append(
                    ToolCallRequest(
                        id=self._sanitize_tool_call_id(tc.id),
                        name=tc.function.name,
                        arguments=args,
                    )
                )

        usage = {}
        if hasattr(response, "usage") and response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        reasoning_content = getattr(message, "reasoning_content", None) or None

        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            usage=usage,
            reasoning_content=reasoning_content,
        )

    def _build_kwargs(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        model: str | None,
        model_params: dict[str, Any] | None,
        stream: bool = False,
    ) -> tuple[str, dict[str, Any]]:
        """Build kwargs for acompletion, shared by chat and chat_stream."""
        original_model = model or self.default_model
        resolved = self._resolve_model(original_model)

        if self._supports_cache_control(original_model):
            messages, tools = self._apply_cache_control(messages, tools)

        params = {"max_tokens": 4096, "temperature": 0.7}
        if model_params:
            params.update(model_params)
        if "max_tokens" in params:
            params["max_tokens"] = max(1, params["max_tokens"])

        # extract thinking level before spreading params into kwargs
        thinking_level = params.pop("thinking", None)
        # remove non-api params that would confuse litellm
        params.pop("context_window", None)

        kwargs: dict[str, Any] = {
            "model": resolved,
            "messages": self._validate_transcript(
                self._sanitize_messages(
                    self._convert_image_blocks(self._sanitize_empty_content(messages))
                )
            ),
            **params,
        }

        # apply thinking/reasoning budget
        if thinking_level and str(thinking_level).lower() != "off":
            thinking_budgets = {"low": 2048, "medium": 8192, "high": 32768}
            budget = thinking_budgets.get(str(thinking_level).lower(), 8192)
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": budget}
            # anthropic requires temperature=1 with extended thinking
            kwargs["temperature"] = 1

        self._apply_model_overrides(resolved, kwargs)

        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.api_base:
            kwargs["api_base"] = self.api_base
        if self.extra_headers:
            kwargs["extra_headers"] = self.extra_headers

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        if stream:
            kwargs["stream"] = True
            kwargs["stream_options"] = {"include_usage": True}

        return original_model, kwargs

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        model_params: dict[str, Any] | None = None,
    ):
        """Stream LLM response tokens."""

        from openbotx.providers.base import StreamChunk
        from openbotx.providers.retry import retry_with_backoff

        original_model, kwargs = self._build_kwargs(
            messages, tools, model, model_params, stream=True
        )

        if not original_model:
            yield StreamChunk(type="content", content="No model configured.")
            yield StreamChunk(type="done")
            return

        try:
            response = await retry_with_backoff(lambda: acompletion(**kwargs))
        except Exception as e:
            from openbotx.providers.errors import (
                ContextOverflowError,
                LLMErrorType,
                classify_error,
            )

            error_type = classify_error(e)
            # context overflow must propagate so the agent loop can compact
            if error_type == LLMErrorType.CONTEXT_OVERFLOW:
                raise ContextOverflowError(str(e)) from e
            safe_msg = self._sanitize_error_message(e)
            yield StreamChunk(type="content", content=f"Error calling LLM: {safe_msg}")
            yield StreamChunk(type="done")
            return

        # accumulate partial tool calls
        partial_tool_calls: dict[int, dict[str, str]] = {}

        async for chunk in response:
            if not chunk.choices:
                # usage-only chunk at the end
                if hasattr(chunk, "usage") and chunk.usage:
                    yield StreamChunk(
                        type="usage",
                        usage={
                            "prompt_tokens": getattr(chunk.usage, "prompt_tokens", 0),
                            "completion_tokens": getattr(chunk.usage, "completion_tokens", 0),
                            "total_tokens": getattr(chunk.usage, "total_tokens", 0),
                        },
                    )
                continue

            delta = chunk.choices[0].delta
            finish_reason = chunk.choices[0].finish_reason

            # content tokens
            if hasattr(delta, "content") and delta.content:
                yield StreamChunk(type="content", content=delta.content)

            # reasoning tokens
            reasoning = getattr(delta, "reasoning_content", None)
            if reasoning:
                yield StreamChunk(type="reasoning", content=reasoning)

            # tool call deltas
            if hasattr(delta, "tool_calls") and delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index if hasattr(tc_delta, "index") else 0
                    if idx not in partial_tool_calls:
                        partial_tool_calls[idx] = {"id": "", "name": "", "arguments": ""}
                    entry = partial_tool_calls[idx]
                    if hasattr(tc_delta, "id") and tc_delta.id:
                        entry["id"] = tc_delta.id
                    if hasattr(tc_delta, "function") and tc_delta.function:
                        if tc_delta.function.name:
                            entry["name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            entry["arguments"] += tc_delta.function.arguments

            # emit completed tool calls
            if finish_reason == "tool_calls" or finish_reason == "stop":
                for idx in sorted(partial_tool_calls):
                    entry = partial_tool_calls[idx]
                    yield StreamChunk(
                        type="tool_call",
                        tool_call_index=idx,
                        tool_call_id=self._sanitize_tool_call_id(entry["id"]),
                        tool_call_name=entry["name"],
                        tool_call_arguments=entry["arguments"],
                    )

            # usage in final chunk
            if hasattr(chunk, "usage") and chunk.usage:
                yield StreamChunk(
                    type="usage",
                    usage={
                        "prompt_tokens": getattr(chunk.usage, "prompt_tokens", 0),
                        "completion_tokens": getattr(chunk.usage, "completion_tokens", 0),
                        "total_tokens": getattr(chunk.usage, "total_tokens", 0),
                    },
                )

        yield StreamChunk(type="done")

    def get_default_model(self) -> str:
        return self.default_model
