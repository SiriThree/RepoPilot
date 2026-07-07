from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    repo_path: Mapped[str] = mapped_column(Text)
    task_input: Mapped[str] = mapped_column(Text)
    base_ref: Mapped[str] = mapped_column(String(128), default="HEAD")
    status: Mapped[str] = mapped_column(String(32), default="pending")
    worktree_path: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text, default="")
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    steps: Mapped[list["RunStep"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="RunStep.step_index"
    )
    command_events: Mapped[list["CommandEvent"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="CommandEvent.created_at"
    )


class RunStep(Base):
    __tablename__ = "run_steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"))
    step_index: Mapped[int] = mapped_column(Integer)
    phase: Mapped[str] = mapped_column(String(32))
    tool_name: Mapped[str] = mapped_column(String(64))
    input_json: Mapped[dict] = mapped_column(JSON, default=dict)
    output_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="completed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    run: Mapped[AgentRun] = relationship(back_populates="steps")


class CommandEvent(Base):
    __tablename__ = "command_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"))
    command: Mapped[str] = mapped_column(Text)
    risk_level: Mapped[str] = mapped_column(String(32))
    approval_status: Mapped[str] = mapped_column(String(32), default="auto_approved")
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stdout_summary: Mapped[str] = mapped_column(Text, default="")
    stderr_summary: Mapped[str] = mapped_column(Text, default="")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    run: Mapped[AgentRun] = relationship(back_populates="command_events")


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(128), default="RepoPilot Benchmark")
    status: Mapped[str] = mapped_column(String(32), default="completed")
    case_count: Mapped[int] = mapped_column(Integer, default=0)
    passed_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_iterations: Mapped[int] = mapped_column(Integer, default=0)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
