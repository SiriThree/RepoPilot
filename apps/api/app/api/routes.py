from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import AgentRun
from app.db.session import get_db
from app.repopilot.benchmark import BenchmarkRunner
from app.repopilot.runtime import RepoPilotRuntime
from app.schemas.repopilot import (
    AgentRunRequest,
    AgentRunResponse,
    ApprovalRequest,
    EvaluationRunRequest,
    EvaluationRunResponse,
)

router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/runs", response_model=AgentRunResponse)
async def create_run(payload: AgentRunRequest, db: Session = Depends(get_db)) -> AgentRun:
    runtime = RepoPilotRuntime(db)
    try:
        run = await runtime.create_and_execute(payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return run


@router.get("/runs", response_model=list[AgentRunResponse])
def list_runs(db: Session = Depends(get_db)) -> list[AgentRun]:
    return db.query(AgentRun).order_by(AgentRun.created_at.desc()).limit(20).all()


@router.get("/runs/{run_id}", response_model=AgentRunResponse)
def get_run(run_id: str, db: Session = Depends(get_db)) -> AgentRun:
    run = db.get(AgentRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.post("/runs/{run_id}/approve", response_model=AgentRunResponse)
async def approve_run(run_id: str, payload: ApprovalRequest, db: Session = Depends(get_db)) -> AgentRun:
    run = db.get(AgentRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    runtime = RepoPilotRuntime(db)
    try:
        updated = await runtime.approve_and_resume(run, payload.command_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return updated


@router.post("/evals", response_model=EvaluationRunResponse)
async def create_eval(payload: EvaluationRunRequest, db: Session = Depends(get_db)):
    runner = BenchmarkRunner(db)
    try:
        evaluation = await runner.create_and_execute(payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return evaluation


@router.get("/evals", response_model=list[EvaluationRunResponse])
def list_evals(db: Session = Depends(get_db)):
    from app.db.models import EvaluationRun

    return db.query(EvaluationRun).order_by(EvaluationRun.created_at.desc()).limit(20).all()
