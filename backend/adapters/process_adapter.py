"""
Process adapter — manages agents as local subprocesses.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
from typing import Any, Optional

from .base import AgentStats, BaseAdapter, DiscoveredAgent

logger = logging.getLogger(__name__)


class ProcessAdapter(BaseAdapter):
    """Manages agents as local subprocess entries."""

    def __init__(self):
        self._processes: dict[str, asyncio.subprocess.Process] = {}

    @property
    def name(self) -> str:
        return "process"

    async def discover_agents(self) -> list[DiscoveredAgent]:
        return [
            DiscoveredAgent(
                external_id=aid,
                name=f"process-{aid}",
                status="working" if p.returncode is None else "stopped",
            )
            for aid, p in self._processes.items()
        ]

    async def get_agent_status(self, agent_id: str) -> Optional[str]:
        p = self._processes.get(agent_id)
        if p is None:
            return None
        return "working" if p.returncode is None else "stopped"

    async def send_command(self, agent_id: str, command: str, params: dict[str, Any]) -> dict[str, Any]:
        if command == "start":
            cmd = params.get("command", "echo agent-started")
            try:
                proc = await asyncio.create_subprocess_shell(
                    cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                self._processes[agent_id] = proc
                return {"success": True, "pid": proc.pid}
            except Exception as exc:
                return {"success": False, "error": str(exc)}

        elif command == "stop":
            p = self._processes.get(agent_id)
            if p and p.returncode is None:
                p.terminate()
                try:
                    await asyncio.wait_for(p.wait(), timeout=10)
                except asyncio.TimeoutError:
                    p.kill()
            return {"success": True}

        elif command == "restart":
            await self.send_command(agent_id, "stop", {})
            return await self.send_command(agent_id, "start", params)

        return {"success": False, "error": f"Unknown command: {command}"}

    async def collect_metrics(self, agent_id: str) -> Optional[AgentStats]:
        p = self._processes.get(agent_id)
        if not p or p.returncode is not None:
            return None
        return AgentStats(cpu_percent=0, memory_mb=0)

    async def shutdown(self) -> None:
        for aid in list(self._processes):
            await self.send_command(aid, "stop", {})
        self._processes.clear()
