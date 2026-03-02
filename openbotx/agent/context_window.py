import json
from typing import Any

# model context limits in tokens
MODEL_CONTEXT_LIMITS: dict[str, int] = {
    # -------------------------
    # OPENAI — GPT series
    # -------------------------
    "gpt-5": 400_000,
    "gpt-5.1": 400_000,
    "gpt-5.2": 400_000,
    "gpt-4.1": 1_000_000,
    "gpt-4.1-mini": 1_000_000,
    "gpt-4.1-nano": 1_000_000,
    "gpt-4o": 128_000,
    "gpt-4o-mini": 128_000,
    "gpt-4-turbo": 128_000,
    "o4": 200_000,
    "o4-mini": 200_000,
    "o3": 200_000,
    "o3-mini": 200_000,
    "gpt-3.5-turbo": 16_385,
    # -------------------------
    # GOOGLE — Gemini & variants
    # -------------------------
    "gemini-3-pro": 1_000_000,
    "gemini-3-flash": 1_000_000,
    "gemini-3.1-pro": 1_000_000,
    "gemini-2.5-pro": 1_000_000,
    "gemini-2.5-flash": 1_000_000,
    "gemini-2.0-pro": 1_000_000,
    "gemini-2.0-flash": 1_000_000,
    # -------------------------
    # ANTHROPIC — Claude family
    # -------------------------
    "claude-opus-4.6": 1_000_000,
    "claude-opus-4.5": 1_000_000,
    "claude-opus-4": 200_000,
    "claude-3.5-sonnet": 200_000,
    "claude-3.5-haiku": 200_000,
    "claude-3-opus": 200_000,
    "claude-3-sonnet": 200_000,
    "claude-3-haiku": 200_000,
    # -------------------------
    # META / LLAMA 4 series
    # -------------------------
    "llama-4-scout": 10_000_000,
    "llama-4-maverick": 1_000_000,
    "llama-4-behemoth": 1_000_000,
    "llama-3.2-90b": 128_000,
    "llama-3.1-405b": 128_000,
    "llama-3.1-70b": 128_000,
    "llama-3.1-8b": 128_000,
    # -------------------------
    # XAI / Grok
    # -------------------------
    "grok-4": 256_000,
    "grok-3": 128_000,
    # -------------------------
    # MOONSHOT AI — Kimi & Moonshot
    # -------------------------
    "kimi-k2.5-instruct": 256_000,
    "kimi-k2.5": 256_000,
    "kimi-k2-instruct": 256_000,
    "kimi-k2": 128_000,
    "kimi-k1.5": 128_000,
    "kimi-k1": 32_000,
    "kimi-linear": 128_000,
    "moonshot-v1-128k": 131_072,
    "moonshot-v1-32k": 32_768,
    "moonshot-v1-8k": 8_192,
    # -------------------------
    # QWEN series (Alibaba)
    # -------------------------
    "qwen3-coder-480b": 262_000,
    "qwen3-30b-a3b": 262_000,
    "qwen3-max": 256_000,
    "qwen3-plus": 128_000,
    "qwen3-turbo": 128_000,
    "qwen2.5-72b": 128_000,
    "qwen2.5-32b": 128_000,
    # -------------------------
    # DEEPSEEK
    # -------------------------
    "deepseek-r1": 164_000,
    "deepseek-v3": 128_000,
    "deepseek-v2": 128_000,
    "deepseek-chat": 64_000,
    "deepseek-coder": 64_000,
    # -------------------------
    # AI21
    # -------------------------
    "jamba-1.6-large": 256_000,
    "jamba-1.6-mini": 256_000,
    # -------------------------
    # COHERE
    # -------------------------
    "command-r+": 128_000,
    "command-r": 128_000,
    # -------------------------
    # OTHER
    # -------------------------
    "glm-4.7-thinking": 200_000,
}

DEFAULT_LIMIT = 100_000
SAFETY_MARGIN = 0.85  # compact when usage exceeds 85% of limit


def get_model_limit(model: str, model_params: dict[str, Any] | None = None) -> int:
    """Resolve context window limit for a model name.

    If model_params contains a "context_window" key, that value takes precedence
    over the built-in MODEL_CONTEXT_LIMITS lookup.
    """
    if model_params and model_params.get("context_window"):
        return int(model_params["context_window"])
    model_lower = model.lower()
    for key, limit in MODEL_CONTEXT_LIMITS.items():
        if key in model_lower:
            return limit
    return DEFAULT_LIMIT


def estimate_tokens(messages: list[dict[str, Any]]) -> int:
    """Estimate token count using chars/4 heuristic with safety margin."""
    total_chars = 0

    for msg in messages:
        content = msg.get("content")
        if isinstance(content, str):
            total_chars += len(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    total_chars += len(str(part.get("text", "")))

        # count tool call arguments
        for tc in msg.get("tool_calls", []):
            func = tc.get("function", {})
            args = func.get("arguments", "")
            if isinstance(args, str):
                total_chars += len(args)
            else:
                total_chars += len(json.dumps(args))

        # count reasoning content
        reasoning = msg.get("reasoning_content")
        if reasoning:
            total_chars += len(reasoning)

    # chars/4 is a conservative estimate, add 20% buffer
    return int((total_chars / 4) * 1.2)


def needs_compaction(
    messages: list[dict[str, Any]],
    model: str,
    model_params: dict[str, Any] | None = None,
) -> bool:
    """Check if messages exceed the safe threshold for the model."""
    limit = get_model_limit(model, model_params)
    estimated = estimate_tokens(messages)
    return estimated > int(limit * SAFETY_MARGIN)
