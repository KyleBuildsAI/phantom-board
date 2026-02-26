"""
WebSocket connection manager for Phantom Board.

Handles client connections, broadcasts real-time updates,
implements heartbeat pings, and supports graceful reconnection.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

logger = logging.getLogger(__name__)


class ConnectionInfo:
    """Metadata about a connected WebSocket client."""

    __slots__ = ("ws", "client_id", "connected_at", "last_ping", "subscriptions")

    def __init__(self, ws: WebSocket, client_id: str) -> None:
        self.ws = ws
        self.client_id = client_id
        self.connected_at = datetime.now(timezone.utc)
        self.last_ping = self.connected_at
        self.subscriptions: set[str] = {"*"}  # subscribe to all by default


class WebSocketManager:
    """
    Manages WebSocket connections for real-time dashboard updates.

    Features:
      - Multiple simultaneous client connections
      - Topic-based subscriptions (agents, tasks, metrics, messages)
      - Heartbeat pings to detect stale connections
      - Broadcast and targeted messaging
      - Graceful disconnection handling
    """

    HEARTBEAT_INTERVAL = 15  # seconds
    PING_TIMEOUT = 30  # seconds before considering a connection dead

    def __init__(self) -> None:
        self._connections: dict[str, ConnectionInfo] = {}
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    @property
    def active_count(self) -> int:
        return len(self._connections)

    @property
    def client_ids(self) -> list[str]:
        return list(self._connections.keys())

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def connect(self, websocket: WebSocket) -> str:
        """Accept a WebSocket connection and register it."""
        await websocket.accept()
        client_id = uuid4().hex[:10]
        info = ConnectionInfo(websocket, client_id)

        async with self._lock:
            self._connections[client_id] = info

        logger.info("WS client connected: %s (total: %d)", client_id, self.active_count)

        # Send welcome message
        await self._send_to(
            info,
            {
                "event": "connected",
                "data": {
                    "client_id": client_id,
                    "server_time": datetime.now(timezone.utc).isoformat(),
                },
            },
        )

        # Start heartbeat if not running
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        return client_id

    async def disconnect(self, client_id: str) -> None:
        """Remove a client connection."""
        async with self._lock:
            info = self._connections.pop(client_id, None)

        if info is not None:
            logger.info(
                "WS client disconnected: %s (total: %d)",
                client_id,
                self.active_count,
            )
            try:
                if info.ws.client_state == WebSocketState.CONNECTED:
                    await info.ws.close()
            except Exception:
                pass

    async def disconnect_all(self) -> None:
        """Close all active connections (used during shutdown)."""
        async with self._lock:
            clients = list(self._connections.values())
            self._connections.clear()

        for info in clients:
            try:
                if info.ws.client_state == WebSocketState.CONNECTED:
                    await info.ws.close(code=1001, reason="Server shutting down")
            except Exception:
                pass

        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        logger.info("All WebSocket connections closed")

    # ------------------------------------------------------------------
    # Message handling
    # ------------------------------------------------------------------

    async def handle_client(self, websocket: WebSocket, client_id: str) -> None:
        """
        Main loop that receives messages from a connected client.
        Runs until the client disconnects.
        """
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    message = json.loads(raw)
                except json.JSONDecodeError:
                    await self._send_to(
                        self._connections.get(client_id),
                        {"event": "error", "data": {"message": "Invalid JSON"}},
                    )
                    continue

                await self._process_client_message(client_id, message)

        except WebSocketDisconnect:
            logger.debug("Client %s sent disconnect frame", client_id)
        except Exception as exc:
            logger.error("Error in WS client %s: %s", client_id, exc)
        finally:
            await self.disconnect(client_id)

    async def _process_client_message(
        self, client_id: str, message: dict[str, Any]
    ) -> None:
        """Route an inbound client message to the appropriate handler."""
        event = message.get("event", "")

        if event == "pong":
            info = self._connections.get(client_id)
            if info:
                info.last_ping = datetime.now(timezone.utc)

        elif event == "subscribe":
            topics = message.get("data", {}).get("topics", [])
            info = self._connections.get(client_id)
            if info and topics:
                info.subscriptions = set(topics)
                await self._send_to(
                    info,
                    {
                        "event": "subscribed",
                        "data": {"topics": list(info.subscriptions)},
                    },
                )

        elif event == "unsubscribe":
            info = self._connections.get(client_id)
            if info:
                info.subscriptions = {"*"}

    # ------------------------------------------------------------------
    # Broadcasting
    # ------------------------------------------------------------------

    async def broadcast(self, event: str, data: dict[str, Any]) -> None:
        """Send an event to all connected clients subscribed to the topic."""
        payload = {
            "event": event,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        topic = event.split(".")[0] if "." in event else event
        stale: list[str] = []

        async with self._lock:
            clients = list(self._connections.items())

        for cid, info in clients:
            if "*" in info.subscriptions or topic in info.subscriptions:
                try:
                    await self._send_to(info, payload)
                except Exception:
                    stale.append(cid)

        for cid in stale:
            await self.disconnect(cid)

    async def send_to_client(
        self, client_id: str, event: str, data: dict[str, Any]
    ) -> bool:
        """Send an event to a specific client."""
        info = self._connections.get(client_id)
        if info is None:
            return False
        payload = {
            "event": event,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        try:
            await self._send_to(info, payload)
            return True
        except Exception:
            await self.disconnect(client_id)
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _send_to(
        self, info: Optional[ConnectionInfo], payload: dict[str, Any]
    ) -> None:
        if info is None:
            return
        if info.ws.client_state != WebSocketState.CONNECTED:
            return
        await info.ws.send_json(payload)

    async def _heartbeat_loop(self) -> None:
        """Periodically ping all clients and prune dead connections."""
        logger.info("Heartbeat loop started")
        try:
            while self._connections:
                await asyncio.sleep(self.HEARTBEAT_INTERVAL)
                now = datetime.now(timezone.utc)
                stale: list[str] = []

                async with self._lock:
                    clients = list(self._connections.items())

                for cid, info in clients:
                    elapsed = (now - info.last_ping).total_seconds()
                    if elapsed > self.PING_TIMEOUT:
                        stale.append(cid)
                        continue
                    try:
                        await self._send_to(
                            info,
                            {"event": "ping", "data": {"server_time": now.isoformat()}},
                        )
                    except Exception:
                        stale.append(cid)

                for cid in stale:
                    logger.warning("Pruning stale WS client: %s", cid)
                    await self.disconnect(cid)

        except asyncio.CancelledError:
            logger.info("Heartbeat loop cancelled")
        except Exception as exc:
            logger.error("Heartbeat loop error: %s", exc)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
ws_manager = WebSocketManager()
