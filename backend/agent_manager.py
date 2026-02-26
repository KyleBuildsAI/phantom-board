"""
Agent lifecycle manager for Phantom Board.

Handles agent registration, status transitions, start/stop/restart
operations, and coordinates with adapters for real execution.
Implements a strict state machine for agent status.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .adapters import get_adapter
from .database import get_managed_session
from .models import Agent, AgentStatus, AgentType, Metric, Task, TaskStatus
from .schemas import AgentCreate, AgentUpdate, WSAgentUpdate
from .websocket import ws_manager

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Valid state transitions
# ---------------------------------------------------------------------------
VALID_TRANSITIONS: dict[AgentStatus, set[AgentStatus]] = {
    AgentStatus.IDLE: {
        AgentStatus.WORKING,
        AgentStatus.STOPPED,
        AgentStatus.STOPPING,
        AgentStatus.ERROR,
    },
    AgentStatus.WORKING: {
        AgentStatus.IDLE,
        AgentStatus.STOPPED,
        AgentStatus.STOPPING,
        AgentStatus.ERROR,
    },
    AgentStatus.STOPPED: {
        AgentStatus.STARTING,
        AgentStatus.IDLE,
        AgentStatus.ERROR,
    },
    AgentStatus.ERROR: {
        AgentStatus.STARTING,
        AgentStatus.IDLE,
        AgentStatus.STOPPED,
    },
    AgentStatus.STARTING: {
        AgentStatus.IDLE,
        AgentStatus.ERROR,
    },
    AgentStatus.STOPPING: {
        AgentStatus.STOPPED,
        AgentStatus.ERROR,
    },
}


class AgentManager:
    """
    Manages the full lifecycle of agents in the system.

    Responsibilities:
      - Registering / deregistering agents
      - Enforcing valid status transitions
      - Coordinating with adapters for start/stop
      - Broadcasting state changes over WebSocket
    """

    def __init__(self) -> None:
        self._agent_locks: dict[str, asyncio.Lock] = {}

    def _get_lock(self, agent_id: str) -> asyncio.Lock:
        if agent_id not in self._agent_locks:
            self._agent_locks[agent_id] = asyncio.Lock()
        return self._agent_locks[agent_id]

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def register_agent(
        self, session: AsyncSession, data: AgentCreate
    ) -> Agent:
        """Create and persist a new agent."""
        agent = Agent(
            name=data.name,
            type=data.type,
            description=data.description,
            config=data.config or {},
            model=data.model,
            adapter=data.adapter or "process",
            position_x=data.position_x,
            position_y=data.position_y,
            status=AgentStatus.IDLE,
        )
        session.add(agent)
        await session.flush()

        logger.info("Registered agent %s (%s)", agent.name, agent.id)

        await ws_manager.broadcast(
            "agent.registered",
            {
                "agent_id": agent.id,
                "name": agent.name,
                "type": agent.type.value,
                "status": agent.status.value,
            },
        )
        return agent

    async def get_agent(self, session: AsyncSession, agent_id: str) -> Optional[Agent]:
        result = await session.execute(select(Agent).where(Agent.id == agent_id))
        return result.scalar_one_or_none()

    async def list_agents(
        self, session: AsyncSession, status: Optional[AgentStatus] = None
    ) -> list[Agent]:
        stmt = select(Agent).order_by(Agent.name)
        if status is not None:
            stmt = stmt.where(Agent.status == status)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def update_agent(
        self, session: AsyncSession, agent_id: str, data: AgentUpdate
    ) -> Optional[Agent]:
        agent = await self.get_agent(session, agent_id)
        if agent is None:
            return None

        update_fields = data.model_dump(exclude_unset=True)

        if "status" in update_fields:
            new_status = update_fields.pop("status")
            if new_status and not self._is_valid_transition(agent.status, new_status):
                raise ValueError(
                    f"Invalid transition: {agent.status.value} -> {new_status.value}"
                )
            agent.status = new_status

        for field, value in update_fields.items():
            setattr(agent, field, value)

        agent.updated_at = datetime.now(timezone.utc)
        await session.flush()

        await ws_manager.broadcast(
            "agent.updated",
            {"agent_id": agent.id, "changes": list(update_fields.keys())},
        )
        return agent

    async def delete_agent(self, session: AsyncSession, agent_id: str) -> bool:
        agent = await self.get_agent(session, agent_id)
        if agent is None:
            return False
        await session.delete(agent)
        await session.flush()

        self._agent_locks.pop(agent_id, None)

        await ws_manager.broadcast(
            "agent.deleted", {"agent_id": agent_id, "name": agent.name}
        )
        logger.info("Deleted agent %s", agent_id)
        return True

    # ------------------------------------------------------------------
    # Lifecycle commands
    # ------------------------------------------------------------------

    async def start_agent(
        self, session: AsyncSession, agent_id: str, params: Optional[dict] = None
    ) -> Agent:
        """Transition an agent to STARTING and then IDLE."""
        lock = self._get_lock(agent_id)
        async with lock:
            agent = await self.get_agent(session, agent_id)
            if agent is None:
                raise ValueError(f"Agent {agent_id} not found")

            self._assert_transition(agent, AgentStatus.STARTING)
            agent.status = AgentStatus.STARTING
            agent.updated_at = datetime.now(timezone.utc)
            await session.flush()
            await self._broadcast_status(agent)

            try:
                adapter = get_adapter(agent.adapter or "process")
                await adapter.send_command(agent.id, "start", params or {})
                agent.status = AgentStatus.IDLE
            except Exception as exc:
                logger.error("Failed to start agent %s: %s", agent_id, exc)
                agent.status = AgentStatus.ERROR
                agent.config = {**(agent.config or {}), "last_error": str(exc)}

            agent.updated_at = datetime.now(timezone.utc)
            await session.flush()
            await self._broadcast_status(agent)
            return agent

    async def stop_agent(self, session: AsyncSession, agent_id: str) -> Agent:
        """Transition an agent to STOPPING and then STOPPED."""
        lock = self._get_lock(agent_id)
        async with lock:
            agent = await self.get_agent(session, agent_id)
            if agent is None:
                raise ValueError(f"Agent {agent_id} not found")

            self._assert_transition(agent, AgentStatus.STOPPING)
            agent.status = AgentStatus.STOPPING
            agent.updated_at = datetime.now(timezone.utc)
            await session.flush()
            await self._broadcast_status(agent)

            try:
                adapter = get_adapter(agent.adapter or "process")
                await adapter.send_command(agent.id, "stop", {})
                agent.status = AgentStatus.STOPPED
            except Exception as exc:
                logger.error("Failed to stop agent %s: %s", agent_id, exc)
                agent.status = AgentStatus.ERROR
                agent.config = {**(agent.config or {}), "last_error": str(exc)}

            agent.updated_at = datetime.now(timezone.utc)
            await session.flush()
            await self._broadcast_status(agent)
            return agent

    async def restart_agent(
        self, session: AsyncSession, agent_id: str
    ) -> Agent:
        """Stop and then start an agent."""
        agent = await self.stop_agent(session, agent_id)
        if agent.status == AgentStatus.STOPPED:
            agent = await self.start_agent(session, agent_id)
        return agent

    # ------------------------------------------------------------------
    # Agent metrics helpers
    # ------------------------------------------------------------------

    async def get_agent_metrics(
        self, session: AsyncSession, agent_id: str, limit: int = 100
    ) -> dict[str, Any]:
        """Retrieve aggregated metrics for an agent."""
        result = await session.execute(
            select(
                func.sum(Metric.tokens_in).label("total_tokens_in"),
                func.sum(Metric.tokens_out).label("total_tokens_out"),
                func.sum(Metric.cost_usd).label("total_cost"),
                func.avg(Metric.latency_ms).label("avg_latency"),
                func.count(Metric.id).label("sample_count"),
            ).where(Metric.agent_id == agent_id)
        )
        row = result.one()

        # Recent time-series
        recent = await session.execute(
            select(Metric)
            .where(Metric.agent_id == agent_id)
            .order_by(Metric.timestamp.desc())
            .limit(limit)
        )
        series = [
            {
                "timestamp": m.timestamp.isoformat(),
                "tokens": m.tokens_in + m.tokens_out,
                "cost": m.cost_usd,
                "latency": m.latency_ms,
                "cpu": m.cpu_percent,
                "memory": m.memory_mb,
            }
            for m in recent.scalars().all()
        ]
        series.reverse()

        return {
            "total_tokens_in": row.total_tokens_in or 0,
            "total_tokens_out": row.total_tokens_out or 0,
            "total_cost": round(row.total_cost or 0.0, 6),
            "avg_latency": round(row.avg_latency or 0.0, 2),
            "sample_count": row.sample_count or 0,
            "series": series,
        }

    async def get_agent_tasks(
        self, session: AsyncSession, agent_id: str, limit: int = 50
    ) -> list[Task]:
        result = await session.execute(
            select(Task)
            .where(Task.agent_id == agent_id)
            .order_by(Task.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # State machine helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_valid_transition(current: AgentStatus, target: AgentStatus) -> bool:
        return target in VALID_TRANSITIONS.get(current, set())

    @staticmethod
    def _assert_transition(agent: Agent, target: AgentStatus) -> None:
        if target not in VALID_TRANSITIONS.get(agent.status, set()):
            raise ValueError(
                f"Cannot transition agent {agent.name} "
                f"from {agent.status.value} to {target.value}"
            )

    @staticmethod
    async def _broadcast_status(agent: Agent) -> None:
        await ws_manager.broadcast(
            "agent.status",
            WSAgentUpdate(
                agent_id=agent.id,
                status=agent.status,
                current_task=None,
            ).model_dump(),
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
agent_manager = AgentManager()
