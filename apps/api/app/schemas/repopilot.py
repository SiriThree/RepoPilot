from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentRunRequest(BaseModel):
    repo_path: str = Field(min_length=1)
    task_input: str = Field(min_length=8, examples=["Fix the failing boundary check in parser and update tests."])
    base_ref: str = Field(default="HEAD")
    approved_commands: list[str] = Field(default_factory=list)


class BenchmarkCase(BaseModel):
    repo_path: str
    task_input: str
    base_ref: str = "HEAD"
    expected_changed_files: list[str] = Field(default_factory=list)
    name: str = "unnamed_case"


class RunStepResponse(BaseModel):
    step_index: int
    phase: str
    tool_name: str
    input_json: dict[str, Any]
    output_json: dict[str, Any]
    status: str

    model_config = {"from_attributes": True}


class CommandEventResponse(BaseModel):
    command: str
    risk_level: str
    approval_status: str
    exit_code: int | None
    stdout_summary: str
    stderr_summary: str
    duration_ms: int

    model_config = {"from_attributes": True}


class AgentRunResponse(BaseModel):
    id: str
    repo_path: str
    task_input: str
    base_ref: str
    status: str
    worktree_path: str
    summary: str
    result: dict[str, Any]
    created_at: datetime
    finished_at: datetime | None
    steps: list[RunStepResponse]
    command_events: list[CommandEventResponse]

    model_config = {"from_attributes": True}


class EvaluationRunRequest(BaseModel):
    name: str = "RepoPilot Benchmark"
    cases_path: str | None = None
    cases: list[BenchmarkCase] = Field(default_factory=list)
    run_baseline: bool = True
    auto_approve_high_risk: bool = True
    write_result_file: bool = True


class EvaluationRunResponse(BaseModel):
    id: str
    name: str
    status: str
    case_count: int
    passed_count: int
    avg_iterations: int
    result: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class ApprovalRequest(BaseModel):
    command_key: str
