class UsageTracker:
    """Accumulates token usage across multiple LLM calls within a task."""

    def __init__(self):
        self._prompt_tokens = 0
        self._completion_tokens = 0
        self._total_tokens = 0

    def record(self, usage: dict[str, int]) -> None:
        """Add usage from a single LLM call."""
        self._prompt_tokens += max(0, usage.get("prompt_tokens", 0))
        self._completion_tokens += max(0, usage.get("completion_tokens", 0))
        self._total_tokens += max(0, usage.get("total_tokens", 0))

    @property
    def total_tokens(self) -> int:
        return self._total_tokens

    def to_dict(self) -> dict[str, int]:
        return {
            "prompt_tokens": self._prompt_tokens,
            "completion_tokens": self._completion_tokens,
            "total_tokens": self._total_tokens,
        }
