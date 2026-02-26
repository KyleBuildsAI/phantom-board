"""
Pydantic schemas for Phantom Board API.

Defines request/response models for all endpoints, ensuring
strict validation and clean serialization to JSON.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from .models import AgentStatus, AgentType, MessageType, TaskStatus


# ---------------------------------------------------------------------------
# Agent Schemas
# ---------------------------------------------------------------------------

class AgentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    type: AgentType = AgentType.WORKER
    description: Optional[str] = None
    config: Optional[dict[str, Any]] = Field(default_factory=dict)
    model: Optional[str] = None
    adapter: Optional[str] = "process"
    position_x: float = 0.0
    position_y: float = 0.0


class AgentCreate(AgentBase):
    pass


class AgentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    type: Optional[AgentType] = None
    description: Optional[str] = None
    config: Optional[dict[str, Any]] = None
    model: Optional[str] = None
    status: Optional[AgentStatus] = None
    position_x: Optional[float] = None
    position_y: Optional[float] = None


class AgentResponse(AgentBase):
    id: str
    status: AgentStatus
    created_at: datetime
    updated_at: datetime
    current_task: Optional[str] = None
    token_count: int = 0
    total_cost: float = 0.0

    model_config = {"from_attributes": True}


class AgentCommand(BaseModel):
    """Command sent to control an agent."""
    action: str = Field(..., pattern="^(start|stop|restart|pause|resume)$")
    params: Optional[dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Task Schemas
# ---------------------------------------------------------------------------

class TaskBase(BaseModel):
    description: str = Field(..., min_length=1)
    priority: int = Field(default=0, ge=0, le=10)
    metadata_: Optional[dict[str, Any]] = Field(default_factory=dict, alias="metadata")


class TaskCreate(TaskBase):
    agent_id: Optional[str] = None


class TaskUpdate(BaseModel):
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    result: Optional[str] = None
    agent_id: Optional[str] = None


class TaskResponse(BaseModel):
    id: str
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    description: str
    status: TaskStatus
    result: Optional[str] = None
    priority: int = 0
    duration_seconds: Optional[float] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Metric Schemas
# ---------------------------------------------------------------------------

class MetricCreate(BaseModel):
    agent_id: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    memory_mb: float = 0.0
    cpu_percent: float = 0.0
    extra: Optional[dict[str, Any]] = None


class MetricResponse(BaseModel):
    id: int
    agent_id: str
    timestamp: datetime
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: float
    memory_mb: float
    cpu_percent: float
    total_tokens: int = 0

    model_config = {"from_attributes": True}


class SystemMetrics(BaseModel):
    """Aggregated system-wide metrics snapshot."""
    total_agents: int = 0
    active_agents: int = 0
    idle_agents: int = 0
    error_agents: int = 0
    total_tasks: int = 0
    pending_tasks: int = 0
    running_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    avg_latency_ms: float = 0.0
    messages_per_minute: float = 0.0
    uptime_seconds: float = 0.0


# ---------------------------------------------------------------------------
# Message Schemas
# ---------------------------------------------------------------------------

class MessageCreate(BaseModel):
    from_agent: str
    to_agent: str
    type: MessageType = MessageType.REQUEST
    content: str = Field(..., min_length=1)
    metadata_: Optional[dict[str, Any]] = Field(default_factory=dict, alias="metadata")


class MessageResponse(BaseModel):
    id: int
    from_agent: str
    to_agent: str
    type: MessageType
    content: str
    timestamp: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# WebSocket Event Schemas
# ---------------------------------------------------------------------------

class WSEvent(BaseModel):
    """Generic WebSocket event wrapper."""
    event: str
    data: dict[str, Any]
    timestamp: datetime = Field(default_factory=lambda: datetime.now())


class WSAgentUpdate(BaseModel):
    """Agent status change pushed via WebSocket."""
    agent_id: str
    status: AgentStatus
    current_task: Optional[str] = None
    metrics: Optional[dict[str, float]] = None


class WSTaskUpdate(BaseModel):
    """Task progress pushed via WebSocket."""
    task_id: str
    status: TaskStatus
    agent_id: Optional[str] = None
    progress: Optional[float] = None


class WSMessageEvent(BaseModel):
    """Inter-agent message pushed via WebSocket."""
    from_agent: str
    to_agent: str
    type: MessageType
    preview: str


# ---------------------------------------------------------------------------
# Connection / Edge Schemas
# ---------------------------------------------------------------------------

class ConnectionResponse(BaseModel):
    """Represents a communication edge between two agents."""
    source: str
    target: str
    message_count: int = 0
    last_active: Optional[datetime] = None
    active: bool = False


# ---------------------------------------------------------------------------
# Generic
# ---------------------------------------------------------------------------

class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    page: int = 1
    page_size: int = 50


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
    uptime_seconds: float = 0.0
    agents: int = 0
    tasks: int = 0
