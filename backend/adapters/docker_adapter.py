"""
Docker adapter — discovers and controls agents running as Docker containers.

Containers are identified by the label: phantom-board.agent=true
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from .base import AgentStats, BaseAdapter, DiscoveredAgent

logger = logging.getLogger(__name__)


class DockerAdapter(BaseAdapter):
    """Manages agents running as Docker containers."""

    def __init__(self):
        self._client = None

    @property
    def name(self) -> str:
        return "docker"

    async def initialize(self) -> None:
        try:
            import docker
            self._client = docker.from_env()
            logger.info("Docker adapter initialized")
        except Exception as exc:
            logger.warning("Docker not available: %s", exc)

    async def discover_agents(self) -> list[DiscoveredAgent]:
        if not self._client:
            return []
        agents = []
        for c in self._client.containers.list(filters={"label": "phantom-board.agent=true"}):
            agents.append(DiscoveredAgent(
                external_id=c.id[:12],
                name=c.labels.get("phantom-board.name", c.name),
                agent_type=c.labels.get("phantom-board.type", "worker"),
                status="working" if c.status == "running" else "stopped",
                metadata={"image": str(c.image.tags[0]) if c.image.tags else "", "container_id": c.id[:12]},
            ))
        return agents

    async def get_agent_status(self, agent_id: str) -> Optional[str]:
        if not self._client:
            return None
        try:
            c = self._client.containers.get(agent_id)
            return "working" if c.status == "running" else "stopped"
        except Exception:
            return None

    async def send_command(self, agent_id: str, command: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self._client:
            return {"success": False, "error": "Docker not available"}
        try:
            c = self._client.containers.get(agent_id)
            if command == "start":
                c.start()
            elif command == "stop":
                c.stop(timeout=10)
            elif command == "restart":
                c.restart(timeout=10)
            return {"success": True}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    async def collect_metrics(self, agent_id: str) -> Optional[AgentStats]:
        if not self._client:
            return None
        try:
            c = self._client.containers.get(agent_id)
            stats = c.stats(stream=False)
            cpu = self._calc_cpu(stats)
            mem = stats.get("memory_stats", {}).get("usage", 0) / (1024 * 1024)
            return AgentStats(cpu_percent=cpu, memory_mb=round(mem, 1))
        except Exception:
            return None

    @staticmethod
    def _calc_cpu(stats: dict) -> float:
        cpu = stats.get("cpu_stats", {})
        pre = stats.get("precpu_stats", {})
        delta = cpu.get("cpu_usage", {}).get("total_usage", 0) - pre.get("cpu_usage", {}).get("total_usage", 0)
        system_delta = cpu.get("system_cpu_usage", 0) - pre.get("system_cpu_usage", 0)
        ncpu = cpu.get("online_cpus", 1)
        if system_delta > 0 and delta > 0:
            return round((delta / system_delta) * ncpu * 100, 2)
        return 0.0

    async def shutdown(self) -> None:
        self._client = None
