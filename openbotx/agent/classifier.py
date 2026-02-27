import logging
from typing import Any

from openbotx.providers.base import LLMProvider

logger = logging.getLogger(__name__)

ROUTE_TOOL = {
    "type": "function",
    "function": {
        "name": "route",
        "description": "Select the best agent to handle this request",
        "parameters": {
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "description": "The name of the selected agent",
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence score between 0 and 1",
                },
            },
            "required": ["agent_name", "confidence"],
        },
    },
}

CLASSIFIER_HISTORY_LIMIT = 20


class AgentClassifier:
    """LLM-based classifier that routes messages to the best agent."""

    def __init__(
        self,
        provider: LLMProvider,
        agents: dict[str, str],
        model: str,
    ):
        self._provider = provider
        self._agents = agents
        self._model = model
        self._agent_names = list(agents.keys())
        self._system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        agents_block = "\n".join(f"- **{name}**: {desc}" for name, desc in self._agents.items())
        return (
            "You are a request classifier. Your job is to determine which agent "
            "is best suited to handle the user's request.\n\n"
            "Available agents:\n"
            f"{agents_block}\n\n"
            "Rules:\n"
            "1. Analyze the user's latest message and the conversation history.\n"
            "2. If the conversation was previously handled by a specific agent, "
            "continue with that agent unless the topic clearly changes.\n"
            "3. Use the `route` tool to select the best agent.\n"
            "4. Always select exactly one agent from the available list."
        )

    async def classify(
        self,
        input_text: str,
        chat_history: list[dict[str, Any]],
    ) -> str:
        """Classify user input and return the best agent name."""
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self._system_prompt},
        ]

        # include recent history for context
        recent = chat_history[-CLASSIFIER_HISTORY_LIMIT:]
        for msg in recent:
            role = msg.get("role")
            content = msg.get("content", "")
            if role in ("user", "assistant") and content:
                entry: dict[str, Any] = {"role": role, "content": content}
                if role == "assistant" and msg.get("agent_name"):
                    entry["content"] = f"[Agent: {msg['agent_name']}] {content}"
                messages.append(entry)

        messages.append({"role": "user", "content": input_text})

        try:
            response = await self._provider.chat(
                messages=messages,
                tools=[ROUTE_TOOL],
                model=self._model,
                model_params={"max_tokens": 256, "temperature": 0.0},
            )

            if response.has_tool_calls:
                for tc in response.tool_calls:
                    if tc.name == "route":
                        agent_name = tc.arguments.get("agent_name", "")
                        if agent_name in self._agent_names:
                            logger.debug(
                                "classified to agent '%s' (confidence: %s)",
                                agent_name,
                                tc.arguments.get("confidence"),
                            )
                            return agent_name
                        logger.warning("classifier returned unknown agent '%s'", agent_name)

        except Exception as e:
            logger.error("classification failed: %s", e, exc_info=True)

        # default to first agent
        return self._agent_names[0]
