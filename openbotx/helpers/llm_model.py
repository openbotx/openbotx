"""Create PydanticAI model string or model instance for OpenBotX."""

import json
from typing import Any

from openbotx.helpers.config import LLMConfig
from openbotx.helpers.logger import get_logger

_logger = get_logger("llm_model")


class LLMProvider:
    """LLM provider for direct calls with tool support (nanobot-style)."""

    def __init__(self, config: LLMConfig):
        self.config = config
        self._init_client()

    def _init_client(self) -> None:
        """Initialize the appropriate LLM client."""
        if self.config.provider == "anthropic" or (
            not self.config.base_url and not self.config.provider == "openrouter"
        ):
            from anthropic import AsyncAnthropic

            api_key = self.config.api_key or None
            self.client = AsyncAnthropic(api_key=api_key)
            self.provider_type = "anthropic"

        elif self.config.provider == "openai" or self.config.base_url:
            from openai import AsyncOpenAI

            self.client = AsyncOpenAI(
                api_key=self.config.api_key or "dummy",
                base_url=self.config.base_url,
            )
            self.provider_type = "openai"

        elif self.config.provider == "openrouter":
            from openai import AsyncOpenAI

            self.client = AsyncOpenAI(
                api_key=self.config.api_key,
                base_url="https://openrouter.ai/api/v1",
            )
            self.provider_type = "openai"

        else:
            raise ValueError(f"Unsupported provider: {self.config.provider}")

    async def chat(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        """Call LLM with messages and optional tools.

        Args:
            messages: List of message dicts with role and content
            tools: Optional list of tool definitions

        Returns:
            Response dict with content, tool_calls, and has_tool_calls
        """
        if self.provider_type == "anthropic":
            return await self._chat_anthropic(messages, tools)
        else:
            return await self._chat_openai(messages, tools)

    async def _chat_anthropic(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None
    ) -> dict[str, Any]:
        """Call Anthropic API."""
        # Extract system message
        system_msg = next((m["content"] for m in messages if m["role"] == "system"), None)
        user_messages = [m for m in messages if m["role"] != "system"]

        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "messages": user_messages,
            "max_tokens": self.config.max_tokens or 4096,
        }

        if system_msg:
            kwargs["system"] = system_msg

        if self.config.temperature is not None:
            kwargs["temperature"] = self.config.temperature

        if tools:
            kwargs["tools"] = tools

        response = await self.client.messages.create(**kwargs)

        # Convert to standard format
        content = ""
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    {
                        "id": block.id,
                        "name": block.name,
                        "arguments": block.input,
                    }
                )

        return {
            "content": content,
            "tool_calls": tool_calls,
            "has_tool_calls": len(tool_calls) > 0,
        }

    async def _chat_openai(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None
    ) -> dict[str, Any]:
        """Call OpenAI-compatible API."""
        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": self.config.max_tokens or 4096,
        }

        if self.config.temperature is not None:
            kwargs["temperature"] = self.config.temperature

        if tools:
            # Convert tools to OpenAI format
            openai_tools = [{"type": "function", "function": t} for t in tools]
            kwargs["tools"] = openai_tools

        response = await self.client.chat.completions.create(**kwargs)

        message = response.choices[0].message

        # Convert to standard format
        content = message.content or ""
        tool_calls = []

        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append(
                    {
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": json.loads(tc.function.arguments),
                    }
                )

        return {
            "content": content,
            "tool_calls": tool_calls,
            "has_tool_calls": len(tool_calls) > 0,
        }


def create_llm_provider(config: LLMConfig) -> LLMProvider:
    """Create LLM provider for direct calls.

    Args:
        config: LLM configuration

    Returns:
        LLM provider instance
    """
    return LLMProvider(config)


def create_pydantic_model(config: LLMConfig) -> str | Any:
    """Create a PydanticAI model string or model instance from config.

    For OpenRouter provider with api_key, returns OpenRouterModel instance.
    For base_url and api_key, returns OpenAIChatModel for OpenAI-compatible endpoints.
    Otherwise returns "provider:model" string and PydanticAI uses env API keys.

    Args:
        config: LLM configuration

    Returns:
        Model string (e.g. "anthropic:claude-3-5-sonnet") or model instance
    """
    if config.provider == "openrouter" and config.api_key:
        from pydantic_ai.models.openrouter import OpenRouterModel
        from pydantic_ai.providers.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(api_key=config.api_key)
        model = OpenRouterModel(config.model, provider=provider)
        _logger.info(
            "openrouter_model_created",
            model=config.model,
        )
        return model

    if config.base_url and config.api_key:
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        provider = OpenAIProvider(base_url=config.base_url, api_key=config.api_key)
        model = OpenAIChatModel(config.model, provider=provider)
        _logger.info(
            "openai_compatible_model_created",
            model=config.model,
            base_url=config.base_url,
        )
        return model

    model_string = f"{config.provider}:{config.model}"
    _logger.info(
        "pydantic_model_string_created",
        model_string=model_string,
    )
    return model_string


def create_model_settings(config: LLMConfig) -> dict[str, Any] | None:
    """Create ModelSettings dict from config.

    Extracts all fields except 'provider' and 'model' and passes them
    to PydanticAI's ModelSettings (e.g., max_tokens, temperature, top_p, etc).

    Args:
        config: LLM configuration

    Returns:
        Dictionary with model settings, or None if no extra settings

    Example:
        >>> config = LLMConfig(
        ...     provider="anthropic",
        ...     model="claude-3-5-sonnet",
        ...     max_tokens=4096,
        ...     temperature=0.7
        ... )
        >>> create_model_settings(config)
        {"max_tokens": 4096, "temperature": 0.7}
    """
    config_dict = config.model_dump()
    config_dict.pop("provider", None)
    config_dict.pop("model", None)
    config_dict.pop("base_url", None)
    config_dict.pop("api_key", None)
    return config_dict if config_dict else None
