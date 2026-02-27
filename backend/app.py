"""
Phantom Board — FastAPI Application

Real-time dashboard backend for monitoring multi-agent AI systems.
Provides REST API + WebSocket for live updates.
"""

import logging
import os
import sys
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Query, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .agent_manager import agent_manager
from .database import close_db, get_session, init_db
from .models import Agent, AgentStatus, Message, Metric, Task, TaskStatus
from .schemas import (
    AgentCommand, AgentCreate, AgentResponse, AgentUpdate,
    HealthResponse, MessageCreate, MessageResponse, MetricCreate,
    MetricResponse, SystemMetrics, TaskCreate, TaskResponse, TaskUpdate,
)
from .websocket import ws_manager

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", stream=sys.stdout)
logger = logging.getLogger("phantom-board")

START_TIME = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Phantom Board...")
    await init_db()
    yield
    await ws_manager.disconnect_all()
    await close_db()
    logger.info("Phantom Board stopped.")


app = FastAPI(
    title="Phantom Board",
    description="Real-time visual dashboard for multi-agent AI systems",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Health ---
@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health(session: AsyncSession = Depends(get_session)):
    agents = (await session.execute(select(func.count(Agent.id)))).scalar() or 0
    tasks = (await session.execute(select(func.count(Task.id)))).scalar() or 0
    return HealthResponse(uptime_seconds=time.time() - START_TIME, agents=agents, tasks=tasks)


# --- System Metrics ---
@app.get("/api/metrics/system", response_model=SystemMetrics, tags=["metrics"])
async def system_metrics(session: AsyncSession = Depends(get_session)):
    agents = (await session.execute(select(Agent))).scalars().all()
    tasks = (await session.execute(select(Task))).scalars().all()
    metrics_agg = (await session.execute(
        select(func.sum(Metric.tokens_in + Metric.tokens_out), func.sum(Metric.cost_usd), func.avg(Metric.latency_ms))
    )).one()
    return SystemMetrics(
        total_agents=len(agents),
        active_agents=sum(1 for a in agents if a.status == AgentStatus.WORKING),
        idle_agents=sum(1 for a in agents if a.status == AgentStatus.IDLE),
        error_agents=sum(1 for a in agents if a.status == AgentStatus.ERROR),
        total_tasks=len(tasks),
        pending_tasks=sum(1 for t in tasks if t.status == TaskStatus.PENDING),
        running_tasks=sum(1 for t in tasks if t.status == TaskStatus.RUNNING),
        completed_tasks=sum(1 for t in tasks if t.status == TaskStatus.COMPLETED),
        failed_tasks=sum(1 for t in tasks if t.status == TaskStatus.FAILED),
        total_tokens=metrics_agg[0] or 0,
        total_cost_usd=round(metrics_agg[1] or 0, 6),
        avg_latency_ms=round(metrics_agg[2] or 0, 2),
        uptime_seconds=time.time() - START_TIME,
    )


# --- Agents CRUD ---
@app.post("/api/agents", tags=["agents"])
async def create_agent(data: AgentCreate, session: AsyncSession = Depends(get_session)):
    agent = await agent_manager.register_agent(session, data)
    return {"id": agent.id, "name": agent.name, "status": agent.status.value}


@app.get("/api/agents", tags=["agents"])
async def list_agents(status: AgentStatus = None, session: AsyncSession = Depends(get_session)):
    agents = await agent_manager.list_agents(session, status)
    return [
        {"id": a.id, "name": a.name, "type": a.type.value, "status": a.status.value,
         "model": a.model, "position_x": a.position_x, "position_y": a.position_y}
        for a in agents
    ]


@app.get("/api/agents/{agent_id}", tags=["agents"])
async def get_agent(agent_id: str, session: AsyncSession = Depends(get_session)):
    agent = await agent_manager.get_agent(session, agent_id)
    if not agent:
        return JSONResponse(status_code=404, content={"error": "Agent not found"})
    metrics = await agent_manager.get_agent_metrics(session, agent_id)
    return {
        "id": agent.id, "name": agent.name, "type": agent.type.value,
        "status": agent.status.value, "description": agent.description,
        "model": agent.model, "config": agent.config, "metrics": metrics,
    }


@app.patch("/api/agents/{agent_id}", tags=["agents"])
async def update_agent(agent_id: str, data: AgentUpdate, session: AsyncSession = Depends(get_session)):
    agent = await agent_manager.update_agent(session, agent_id, data)
    if not agent:
        return JSONResponse(status_code=404, content={"error": "Agent not found"})
    return {"id": agent.id, "status": agent.status.value}


@app.delete("/api/agents/{agent_id}", tags=["agents"])
async def delete_agent(agent_id: str, session: AsyncSession = Depends(get_session)):
    ok = await agent_manager.delete_agent(session, agent_id)
    if not ok:
        return JSONResponse(status_code=404, content={"error": "Agent not found"})
    return {"deleted": True}


@app.post("/api/agents/{agent_id}/command", tags=["agents"])
async def send_command(agent_id: str, cmd: AgentCommand, session: AsyncSession = Depends(get_session)):
    if cmd.action == "start":
        agent = await agent_manager.start_agent(session, agent_id, cmd.params)
    elif cmd.action == "stop":
        agent = await agent_manager.stop_agent(session, agent_id)
    elif cmd.action == "restart":
        agent = await agent_manager.restart_agent(session, agent_id)
    else:
        return JSONResponse(status_code=400, content={"error": f"Unknown action: {cmd.action}"})
    return {"id": agent.id, "status": agent.status.value}


# --- Tasks ---
@app.post("/api/tasks", tags=["tasks"])
async def create_task(data: TaskCreate, session: AsyncSession = Depends(get_session)):
    task = Task(description=data.description, priority=data.priority, agent_id=data.agent_id)
    session.add(task)
    await session.flush()
    await ws_manager.broadcast("task.created", {"task_id": task.id, "description": task.description})
    return {"id": task.id}


@app.get("/api/tasks", tags=["tasks"])
async def list_tasks(
    status: TaskStatus = None,
    limit: int = Query(50, le=200),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Task).order_by(Task.created_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(Task.status == status)
    result = await session.execute(stmt)
    return [
        {"id": t.id, "description": t.description, "status": t.status.value,
         "agent_id": t.agent_id, "priority": t.priority}
        for t in result.scalars().all()
    ]


# --- Metrics ---
@app.post("/api/metrics", tags=["metrics"])
async def record_metric(data: MetricCreate, session: AsyncSession = Depends(get_session)):
    metric = Metric(**data.model_dump())
    session.add(metric)
    await session.flush()
    await ws_manager.broadcast("metric.recorded", {
        "agent_id": data.agent_id, "tokens": data.tokens_in + data.tokens_out, "cost": data.cost_usd
    })
    return {"id": metric.id}


# --- Messages ---
@app.post("/api/messages", tags=["messages"])
async def send_message(data: MessageCreate, session: AsyncSession = Depends(get_session)):
    msg = Message(from_agent=data.from_agent, to_agent=data.to_agent, type=data.type, content=data.content)
    session.add(msg)
    await session.flush()
    await ws_manager.broadcast("message.sent", {
        "from": data.from_agent, "to": data.to_agent, "type": data.type.value
    })
    return {"id": msg.id}


@app.get("/api/connections", tags=["messages"])
async def get_connections(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Message.from_agent, Message.to_agent, func.count(Message.id).label("count"))
        .group_by(Message.from_agent, Message.to_agent)
    )
    return [{"source": r[0], "target": r[1], "message_count": r[2]} for r in result.all()]


# --- WebSocket ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    client_id = await ws_manager.connect(websocket)
    await ws_manager.handle_client(websocket, client_id)
