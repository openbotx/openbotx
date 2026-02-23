"""Agent brain for OpenBotX with manual agentic loop (nanobot-style)."""

import inspect
import json
from typing import Any

from openbotx.agent.prompt_builder import (
    create_prompt_builder,
    load_bootstrap_from_workspace,
)
from openbotx.agent.prompts import get_system_context
from openbotx.core.skills_registry import SkillsRegistry
from openbotx.core.tools_registry import ToolsRegistry
from openbotx.helpers.config import get_config
from openbotx.helpers.logger import get_logger
from openbotx.models.message import InboundMessage, MessageContext
from openbotx.models.response import AgentResponse
from openbotx.models.skill import SkillDefinition


class AgentBrain:
    """Brain for processing messages with manual agentic loop."""

    def __init__(
        self,
        skills_registry: SkillsRegistry | None = None,
        tools_registry: ToolsRegistry | None = None,
    ) -> None:
        """Initialize agent brain.

        Args:
            skills_registry: Skills registry
            tools_registry: Tools registry
        """
        self._skills_registry = skills_registry
        self._tools_registry = tools_registry
        self._config = get_config().llm
        self._logger = get_logger("agent_brain")
        self._provider: Any = None
        self._max_iterations = 20

    async def initialize(self) -> None:
        """Initialize the agent and LLM provider."""
        from openbotx.helpers.llm_model import create_llm_provider

        # Create LLM provider for direct calls (nanobot-style loop)
        self._provider = create_llm_provider(self._config)

        self._logger.info(
            "agent_initialized",
            model=f"{self._config.provider}:{self._config.model}",
            max_iterations=self._max_iterations,
        )

    def _build_context_prompt(
        self,
        context: MessageContext,
        matching_skills: list[SkillDefinition],
    ) -> str:
        """Build context prompt for the agent.

        Uses the modular prompt builder with directive awareness.
        Supports dual summaries (user profile + conversation context).

        Args:
            context: Message context
            matching_skills: Skills that match the request

        Returns:
            Context prompt string
        """
        builder = create_prompt_builder()

        # Set prompt mode from context
        builder.with_mode(context.prompt_mode)

        # Add system context
        builder.set_context(get_system_context())

        # Add workspace bootstrap if configured (nanobot-style)
        workspace_path = get_config().paths.workspace
        if workspace_path:
            bootstrap = load_bootstrap_from_workspace(workspace_path)
            if bootstrap:
                builder.set_bootstrap(bootstrap)

        # Add memory context if available
        if context.history or context.summary:
            builder.set_memory(
                summary=context.summary,
                history=context.history,
                user_summary=context.user_summary,
                conversation_summary=context.conversation_summary,
            )

        # Add skills context if available
        if matching_skills:
            skills_data = [
                {
                    "id": s.id,
                    "name": s.name,
                    "description": s.description,
                    "triggers": s.triggers.keywords if s.triggers else [],
                }
                for s in matching_skills
            ]

            # Get detailed skill content
            detailed_skills = []
            for skill in matching_skills:
                if skill.content:
                    detailed_skills.append((skill.name, skill.get_context()))

            builder.set_skills(skills_data, detailed_skills if detailed_skills else None)

        # Add available tools
        if context.available_tools:
            tools_data = []
            if self._tools_registry:
                for name in context.available_tools:
                    tool = self._tools_registry.get(name)
                    if tool:
                        tools_data.append(
                            {
                                "name": tool.definition.name,
                                "description": tool.definition.description,
                            }
                        )
            else:
                tools_data = [{"name": t, "description": ""} for t in context.available_tools]

            builder.set_tools(tools_data)

        # Enable reasoning if requested
        if context.show_reasoning:
            builder.enable_reasoning()

        return builder.build()

    def _build_tool_definitions(self) -> list[dict[str, Any]]:
        """Build tool definitions for LLM from registry.

        Returns:
            List of tool definition dicts
        """
        tools = []
        if not self._tools_registry:
            return tools

        for tool_def in self._tools_registry.list_tools():
            tool = self._tools_registry.get(tool_def.name)
            if not tool or not tool.callable:
                continue

            # Build parameter schema from callable signature
            sig = inspect.signature(tool.callable)
            parameters: dict[str, Any] = {"type": "object", "properties": {}, "required": []}

            for param_name, param in sig.parameters.items():
                if param_name in ["self", "cls"]:
                    continue

                param_type = "string"  # default
                if param.annotation != inspect.Parameter.empty:
                    ann_str = str(param.annotation)
                    if "int" in ann_str:
                        param_type = "integer"
                    elif "bool" in ann_str:
                        param_type = "boolean"
                    elif "float" in ann_str:
                        param_type = "number"

                parameters["properties"][param_name] = {
                    "type": param_type,
                    "description": "",
                }

                if param.default == inspect.Parameter.empty:
                    parameters["required"].append(param_name)

            tools.append(
                {
                    "name": tool_def.name,
                    "description": tool_def.description or "",
                    "parameters": parameters,
                }
            )

        return tools

    async def process(
        self,
        message: InboundMessage,
        context: MessageContext,
    ) -> AgentResponse:
        """Process a message with manual agentic loop (nanobot-style).

        Args:
            message: Inbound message
            context: Message context

        Returns:
            Agent response
        """
        self._logger.info(
            "processing_message",
            message_id=message.id,
            channel_id=message.channel_id,
        )

        # Find matching skills
        matching_skills = []
        if self._skills_registry and message.text:
            matching_skills = self._skills_registry.find_matching_skills(
                message.text,
                limit=3,
            )

        # Build context prompt
        context_prompt = self._build_context_prompt(context, matching_skills)

        # Build tool definitions
        tool_definitions = self._build_tool_definitions()

        # Build initial messages
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": context_prompt},
            {"role": "user", "content": message.text},
        ]

        # Agent loop (similar to nanobot)
        iteration = 0
        final_content = None
        response = AgentResponse()

        while iteration < self._max_iterations:
            iteration += 1

            self._logger.debug(
                "agent_iteration",
                iteration=iteration,
                max=self._max_iterations,
            )

            # Call LLM
            llm_response = await self._provider.chat(messages, tool_definitions)

            # Handle tool calls
            if llm_response["has_tool_calls"]:
                # Add assistant message with tool calls
                assistant_content: Any = llm_response["content"]

                # For Anthropic, build content blocks
                if llm_response["tool_calls"] and self._config.provider == "anthropic":
                    content_blocks = []
                    if llm_response["content"]:
                        content_blocks.append({"type": "text", "text": llm_response["content"]})

                    for tc in llm_response["tool_calls"]:
                        content_blocks.append(
                            {
                                "type": "tool_use",
                                "id": tc["id"],
                                "name": tc["name"],
                                "input": tc["arguments"],
                            }
                        )

                    assistant_content = content_blocks

                messages.append({"role": "assistant", "content": assistant_content})

                # Execute tools
                for tool_call in llm_response["tool_calls"]:
                    tool_name = tool_call["name"]
                    tool_args = tool_call["arguments"]
                    tool_id = tool_call["id"]

                    self._logger.debug(
                        "executing_tool",
                        tool=tool_name,
                        args=tool_args,
                    )

                    # Execute tool
                    tool = self._tools_registry.get(tool_name) if self._tools_registry else None
                    if tool and tool.callable:
                        try:
                            if inspect.iscoroutinefunction(tool.callable):
                                result = await tool.callable(**tool_args)
                            else:
                                result = tool.callable(**tool_args)

                            # Convert ToolResult to string
                            if hasattr(result, "to_string"):
                                result_text = result.to_string()
                            else:
                                result_text = str(result)

                            # Add to response tracking
                            response.tools_called.append(tool_name)

                            # Add tool result to messages (Anthropic format)
                            if self._config.provider == "anthropic":
                                messages.append(
                                    {
                                        "role": "user",
                                        "content": [
                                            {
                                                "type": "tool_result",
                                                "tool_use_id": tool_id,
                                                "content": result_text,
                                            }
                                        ],
                                    }
                                )
                            else:
                                # OpenAI format
                                messages.append(
                                    {
                                        "role": "tool",
                                        "tool_call_id": tool_id,
                                        "name": tool_name,
                                        "content": result_text,
                                    }
                                )

                        except Exception as e:
                            self._logger.error(
                                "tool_execution_error",
                                tool=tool_name,
                                error=str(e),
                            )

                            # Add error to messages
                            if self._config.provider == "anthropic":
                                messages.append(
                                    {
                                        "role": "user",
                                        "content": [
                                            {
                                                "type": "tool_result",
                                                "tool_use_id": tool_id,
                                                "content": f"Error: {str(e)}",
                                                "is_error": True,
                                            }
                                        ],
                                    }
                                )
                            else:
                                messages.append(
                                    {
                                        "role": "tool",
                                        "tool_call_id": tool_id,
                                        "name": tool_name,
                                        "content": f"Error: {str(e)}",
                                    }
                                )
                    else:
                        self._logger.warning("tool_not_found", tool=tool_name)

                        # Add tool not found error
                        if self._config.provider == "anthropic":
                            messages.append(
                                {
                                    "role": "user",
                                    "content": [
                                        {
                                            "type": "tool_result",
                                            "tool_use_id": tool_id,
                                            "content": f"Error: Tool '{tool_name}' not found",
                                            "is_error": True,
                                        }
                                    ],
                                }
                            )
                        else:
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tool_id,
                                    "name": tool_name,
                                    "content": f"Error: Tool '{tool_name}' not found",
                                }
                            )

            else:
                # No tool calls, we're done
                final_content = llm_response["content"]
                break

        if final_content is None:
            final_content = "Task processing completed (max iterations reached)."

        # Add final response
        response.add_text(final_content)

        self._logger.info(
            "processing_complete",
            iterations=iteration,
            tools_called=len(response.tools_called),
        )

        return response

    async def learn_skill(
        self,
        topic: str,
        context: MessageContext,
    ) -> SkillDefinition | None:
        """Learn and create a new skill using the skill generator.

        Args:
            topic: Topic to learn about
            context: Message context

        Returns:
            Created skill or None
        """
        if not self._skills_registry:
            return None

        self._logger.info("learning_skill", topic=topic)

        try:
            from openbotx.core.skill_generator import (
                SkillGenerationRequest,
                SkillGenerator,
            )

            if not self._config.api_key:
                self._logger.warning("learn_skill_no_api_key")
                return None

            generator = SkillGenerator(
                api_key=self._config.api_key,
                model=self._config.model,
                provider=self._config.provider,
                base_url=self._config.base_url,
            )

            # Build context for generation
            context_str = ""
            if context.history:
                recent = context.history[-5:]
                context_str = "\n".join(
                    f"{m.get('role', 'user')}: {m.get('content', '')[:200]}" for m in recent
                )

            # Generate skill
            request = SkillGenerationRequest(
                topic=topic,
                context=context_str,
                channel_id=context.message.channel_id,
                user_id=context.message.user_id,
                required_tools=(context.available_tools[:5] if context.available_tools else []),
            )

            result = await generator.generate(request)

            if not result.success or not result.skill:
                self._logger.warning(
                    "skill_generation_failed",
                    topic=topic,
                    error=result.error,
                )
                return None

            # Save the generated skill
            skill = await self._skills_registry.create_skill(
                skill_id=result.skill.id,
                name=result.skill.name,
                description=result.skill.description,
                triggers=(
                    result.skill.triggers.keywords if result.skill.triggers else [topic.lower()]
                ),
                tools=result.skill.tools,
                steps=result.skill.steps,
                guidelines=result.skill.guidelines,
            )

            self._logger.info(
                "skill_learned",
                skill_id=skill.id,
                name=skill.name,
            )

            return skill

        except Exception as e:
            self._logger.error("learn_skill_error", error=str(e))
            return None


# Global agent brain instance
_agent_brain: AgentBrain | None = None


def get_agent_brain() -> AgentBrain:
    """Get the global agent brain instance."""
    global _agent_brain
    if _agent_brain is None:
        _agent_brain = AgentBrain()
    return _agent_brain


def set_agent_brain(brain: AgentBrain) -> None:
    """Set the global agent brain instance."""
    global _agent_brain
    _agent_brain = brain
