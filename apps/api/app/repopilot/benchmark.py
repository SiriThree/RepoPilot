import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import EvaluationRun
from app.repopilot.runtime import RepoPilotRuntime
from app.schemas.repopilot import AgentRunRequest, BenchmarkCase, EvaluationRunRequest


class BenchmarkRunner:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.runtime = RepoPilotRuntime(db)

    async def create_and_execute(self, payload: EvaluationRunRequest) -> EvaluationRun:
        cases = self._load_cases(payload)
        if not cases:
            raise ValueError("No benchmark cases provided")

        results: list[dict] = []
        passed = 0
        iteration_sum = 0
        failure_breakdown: dict[str, int] = {}
        failed_phase_breakdown: dict[str, int] = {}
        failed_command_breakdown: dict[str, int] = {}

        for case in cases:
            run = await self.runtime.create_and_execute(
                AgentRunRequest(repo_path=case.repo_path, task_input=case.task_input, base_ref=case.base_ref)
            )
            success = bool(run.result.get("tests_passed"))
            changed_files = run.result.get("files_changed", [])
            expected_match = not case.expected_changed_files or changed_files == case.expected_changed_files
            case_passed = success and expected_match
            passed += int(case_passed)
            iteration_sum += int(run.result.get("iterations", 0))
            failure_reason = run.result.get("failure_reason") or ("expected_files_mismatch" if not expected_match else None)
            failed_step = run.steps[-1] if run.steps else None
            failed_command = run.command_events[-1] if run.command_events else None
            if failure_reason:
                failure_breakdown[failure_reason] = failure_breakdown.get(failure_reason, 0) + 1
            if failure_reason and failed_step:
                failed_phase_breakdown[failed_step.phase] = failed_phase_breakdown.get(failed_step.phase, 0) + 1
            if failure_reason and failed_command:
                failed_command_breakdown[failed_command.command] = failed_command_breakdown.get(failed_command.command, 0) + 1
            results.append(
                {
                    "name": case.name,
                    "run_id": run.id,
                    "repo_path": case.repo_path,
                    "success": case_passed,
                    "tests_passed": success,
                    "iterations": run.result.get("iterations", 0),
                    "files_changed": changed_files,
                    "expected_changed_files": case.expected_changed_files,
                    "failure_reason": failure_reason,
                    "failed_phase": failed_step.phase if failure_reason and failed_step else None,
                    "failed_command": failed_command.command if failure_reason and failed_command else None,
                    "failed_command_risk": failed_command.risk_level if failure_reason and failed_command else None,
                    "summary": run.summary,
                }
            )

        evaluation = EvaluationRun(
            name=payload.name,
            status="completed",
            case_count=len(cases),
            passed_count=passed,
            avg_iterations=round(iteration_sum / len(cases)),
            result={
                "pass_rate": round(passed / len(cases), 4),
                "failure_breakdown": failure_breakdown,
                "failed_phase_breakdown": failed_phase_breakdown,
                "failed_command_breakdown": failed_command_breakdown,
                "cases": results,
            },
        )
        self.db.add(evaluation)
        self.db.commit()
        self.db.refresh(evaluation)
        return evaluation

    def _load_cases(self, payload: EvaluationRunRequest) -> list[BenchmarkCase]:
        if payload.cases:
            return payload.cases

        if not payload.cases_path:
            default_path = (Path(__file__).resolve().parents[4] / self.settings.benchmark_dir).resolve()
            if default_path.exists():
                return self._read_case_file(default_path / "sample_cases.json")
            return []

        path = Path(payload.cases_path)
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
        return self._read_case_file(path)

    def _read_case_file(self, path: Path) -> list[BenchmarkCase]:
        if not path.exists():
            raise FileNotFoundError(f"Benchmark case file not found: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        return [BenchmarkCase(**case) for case in payload["cases"]]
