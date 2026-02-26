"""
SQLAlchemy ORM models for Phantom Board.

Defines the core entities: Agent, Task, Metric, and Message.
Each model maps to a database table and includes relationships
for efficient querying of related data.
"""

import enum
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid4().hex[:12]


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class AgentStatus(str, enum.Enum):
    IDLE = "idle"
    WORKING = "working"
    STOPPED = "stopped"
    ERROR = "error"
    STARTING = "starting"
    STOPPING = "stopping"


class AgentType(str, enum.Enum):
    LLM = "llm"
    TOOL = "tool"
    ORCHESTRATOR = "orchestrator"
    WORKER = "worker"
    ROUTER = "router"
    CUSTOM = "custom"


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MessageType(str, enum.Enum):
    REQUEST = "request"
    RESPONSE = "response"
    EVENT = "event"
    HEARTBEAT = "heartbeat"
    COMMAND = "command"


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    type: Mapped[AgentType] = mapped_column(Enum(AgentType), default=AgentType.WORKER)
    status: Mapped[AgentStatus] = mapped_column(
        Enum(AgentStatus), default=AgentStatus.IDLE, index=True
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    model: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    adapter: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, default="process"
    )
    position_x: Mapped[float] = mapped_column(Float, default=0.0)
    position_y: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    # Relationships
    tasks: Mapped[list["Task"]] = relationship(
        "Task", back_populates="agent", cascade="all, delete-orphan"
    )
    metrics: Mapped[list["Metric"]] = relationship(
        "Metric", back_populates="agent", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Agent {self.name} ({self.status.value})>"


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    agent_id: Mapped[Optional[str]] = mapped_column(
        String(32), ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), default=TaskStatus.PENDING, index=True
    )
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    metadata_: Mapped[Optional[dict]] = mapped_column(
        "metadata", JSON, nullable=True, default=dict
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # Relationships
    agent: Mapped[Optional["Agent"]] = relationship("Agent", back_populates="tasks")

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def __repr__(self) -> str:
        return f"<Task {self.id} [{self.status.value}]>"


# ---------------------------------------------------------------------------
# Metric
# ---------------------------------------------------------------------------

class Metric(Base):
    __tablename__ = "metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    memory_mb: Mapped[float] = mapped_column(Float, default=0.0)
    cpu_percent: Mapped[float] = mapped_column(Float, default=0.0)
    extra: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Relationships
    agent: Mapped["Agent"] = relationship("Agent", back_populates="metrics")

    @property
    def total_tokens(self) -> int:
        return self.tokens_in + self.tokens_out

    def __repr__(self) -> str:
        return f"<Metric agent={self.agent_id} tokens={self.total_tokens}>"


# ---------------------------------------------------------------------------
# Message (inter-agent communication log)
# ---------------------------------------------------------------------------

class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    from_agent: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    to_agent: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    type: Mapped[MessageType] = mapped_column(
        Enum(MessageType), default=MessageType.REQUEST
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[Optional[dict]] = mapped_column(
        "metadata", JSON, nullable=True, default=dict
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )

    def __repr__(self) -> str:
        return f"<Message {self.from_agent} -> {self.to_agent}>"
