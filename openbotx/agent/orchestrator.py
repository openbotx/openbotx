from __future__ import annotations

import asyncio
import logging

from openbotx.agent.classifier import AgentClassifier
from openbotx.agent.loop import AgentLoop
from openbotx.bus.events import InboundMessage
from openbotx.bus.queue import MessageBus
from openbotx.session.manager import SessionManager

logger = logging.getLogger(__name__)


class Orchestrator:
    """Consumes messages from the bus and routes them to the appropriate agent."""

    def __init__(
        self,
        bus: MessageBus,
        agents: dict[str, AgentLoop],
        classifier: AgentClassifier | None,
        default_agent: str,
        session_manager: SessionManager,
    ):
        self._bus = bus
        self._agents = agents
        self._classifier = classifier
        self._default_agent = default_agent
        self._session_manager = session_manager
        self._stop_event = asyncio.Event()

    async def run(self) -> None:
        agent_names = ", ".join(self._agents.keys())
        logger.info("orchestrator started (agents: %s)", agent_names)
        while not self._stop_event.is_set():
            try:
                msg = await asyncio.wait_for(self._bus.consume_inbound(), timeout=1.0)
                agent_name = await self._route(msg)
                agent = self._agents[agent_name]
                await agent.process_message(msg, agent_name=agent_name)
            except TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("orchestrator error: %s", e, exc_info=True)

    async def stop(self) -> None:
        self._stop_event.set()
        for agent in self._agents.values():
            await agent.stop()

    async def _route(self, msg: InboundMessage) -> str:
        # single agent or no classifier — skip classification
        if len(self._agents) == 1 or not self._classifier:
            return self._default_agent

        session = self._session_manager.get_or_create(msg.session_key)
        history = session.get_history(max_messages=20)
        return await self._classifier.classify(msg.content, history)
