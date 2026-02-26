"""
Abstract base adapter interface.

All runtime adapters (Docker, process, Kubernetes, etc.) must
implement this interface to integrate with Phantom Board.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class DiscoveredAgent:
    """An agent discovered by an adapter."""
    external_id: str
    name: str
    agent_type: str = "worker"
    status: str = "idle"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentStats:
    """Runtime statistics for an agent."""
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    uptime_seconds: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)


class BaseAdapter(ABC):
    """
    Abstract interface for agent runtime adapters.

    An adapter knows how to:
      1. Discover agents in its runtime environment
      2. Query the current status of an agent
      3. Send lifecycle commands (start, stop, etc.)
      4. Collect runtime metrics/statistics
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable adapter name."""
        ...

    @abstractmethod
    async def discover_agents(self) -> list[DiscoveredAgent]:
        """
        Scan the runtime for agents and return a list of discovered agents.
        This is used for auto-importing agents into Phantom Board.
        """
        ...

    @abstractmethod
    async def get_agent_status(self, agent_id: str) -> Optional[str]:
        """
        Query the runtime status of an agent.
        Returns a status string or None if the agent is not found.
        """
        ...

    @abstractmethod
    async def send_command(
        self, agent_id: str, command: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Send a lifecycle command to an agent.

        Commands include: start, stop, restart, pause, resume
        Returns a result dict with at least {"success": bool}.
        """
        ...

    @abstractmethod
    async def collect_metrics(self, agent_id: str) -> Optional[AgentStats]:
        """
        Collect current runtime metrics for an agent.
        Returns AgentStats or None if unavailable.
        """
        ...

    async def initialize(self) -> None:
        """Optional hook called when the adapter is first loaded."""
        pass

    async def shutdown(self) -> None:
        """Optional hook called during application shutdown."""
        pass
