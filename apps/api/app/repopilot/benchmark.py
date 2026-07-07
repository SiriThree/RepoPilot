import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import AgentRun, EvaluationRun
from app.repopilot.repo_manager import RepoManager
from app.repopilot.runtime import RepoPilotRuntime
from app.repopilot.tools import RepoTools
from app.schemas.repopilot import AgentRunRequest, BenchmarkCase, EvaluationRunRequest


class SingleShotBaseline:
    """A deliberately small one-shot patcher used as an evaluation baseline."""

    def __init__(self) -> None:
        self.repo_manager = RepoManager()
        self.tools = RepoTools()

    def execute(self, case: BenchmarkCase) -> dict:
        repo_path = self.repo_manager.prepare_repo(case.repo_path, case.repo_url)
        worktree_path = self.repo_manager.create_worktree(repo_path, f"baseline-{uuid4()}", case.base_ref)
        initial_test = self.tools.run_tests(worktree_path, case.test_command)
        patch_applied = False
        patch_error = ""

        if initial_test["exit_code"] != 0:
            try:
                source_file = self._select_source_file(worktree_path)
                content = self.tools.read_file(worktree_path, source_file)["content"]
                if "if value < 0:" in content and ("zero" in case.task_input.lower() or "boundary" in case.task_input.lower()):
                    self.tools.apply_patch(worktree_path, source_file, "if value < 0:", "if value <= 0:")
                    patch_applied = True
                else:
                    patch_error = "single-shot baseline did not match a known repair rule"
            except Exception as exc:
                patch_error = str(exc)

        final_test = self.tools.run_tests(worktree_path, case.test_command)
        diff_result = self.tools.git_diff(worktree_path)
        changed_files = self._extract_changed_files(diff_result["stdout"])
        unauthorized_files = self._unauthorized_files(changed_files, case.expected_changed_files)
        success = final_test["exit_code"] == 0 and not unauthorized_files

        return {
            "success": success,
            "tests_passed": final_test["exit_code"] == 0,
            "patch_applied": patch_applied,
            "patch_error": patch_error,
            "files_changed": changed_files,
            "unauthorized_files": unauthorized_files,
            "initial_exit_code": initial_test["exit_code"],
            "final_exit_code": final_test["exit_code"],
        }

    def _select_source_file(self, worktree_path: Path) -> str:
        source_files = sorted(worktree_path.rglob("*.py"))
        candidates = [path for path in source_files if "tests" not in path.parts and path.name != "__init__.py"]
        if not candidates:
            raise ValueError("No Python source file found for baseline repair")
        return candidates[0].relative_to(worktree_path).as_posix()

    def _extract_changed_files(self, diff_text: str) -> list[str]:
        files: list[str] = []
        for line in diff_text.splitlines():
            if line.startswith("diff --git"):
                parts = line.split()
                if len(parts) >= 4:
                    files.append(parts[2].removeprefix("a/"))
        return files

    def _unauthorized_files(self, changed_files: list[str], expected_changed_files: list[str]) -> list[str]:
        if not expected_changed_files:
            return []
        expected = set(expected_changed_files)
        return [path for path in changed_files if path not in expected]


class BenchmarkRunner:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.runtime = RepoPilotRuntime(db)
        self.baseline = SingleShotBaseline()
        self.project_root = Path(__file__).resolve().parents[4]

    async def create_and_execute(self, payload: EvaluationRunRequest) -> EvaluationRun:
        cases = self._load_cases(payload)
        if not cases:
            raise ValueError("No benchmark cases provided")

        results: list[dict] = []
        passed = 0
        baseline_passed = 0
        iteration_sum = 0
        high_risk_intercepted = 0
        unauthorized_modification_count = 0
        failure_breakdown: dict[str, int] = {}
        failed_phase_breakdown: dict[str, int] = {}
        failed_command_breakdown: dict[str, int] = {}

        for case in cases:
            baseline_result = self.baseline.execute(case) if payload.run_baseline else None
            baseline_passed += int(bool(baseline_result and baseline_result["success"]))

            run = await self.runtime.create_and_execute(
                AgentRunRequest(
                    repo_path=case.repo_path,
                    repo_url=case.repo_url,
                    task_input=case.task_input,
                    base_ref=case.base_ref,
                    test_command=case.test_command,
                    issue_text=case.issue_text,
                    issue_url=case.issue_url,
                    ground_truth_pr=case.ground_truth_pr,
                    ground_truth_commit=case.ground_truth_commit,
                )
            )
            intercepted_for_case = self._count_pending_high_risk(run)
            high_risk_intercepted += intercepted_for_case
            if run.status == "awaiting_approval" and payload.auto_approve_high_risk:
                pending = run.result.get("pending_approval") or {}
                command_key = pending.get("command_key")
                if command_key:
                    run = await self.runtime.approve_and_resume(run, command_key)

            success = bool(run.result.get("tests_passed"))
            changed_files = run.result.get("files_changed", [])
            unauthorized_files = self._unauthorized_files(changed_files, case.expected_changed_files)
            unauthorized_modification_count += int(bool(unauthorized_files))
            expected_match = not unauthorized_files
            case_passed = success and expected_match
            passed += int(case_passed)
            iteration_sum += int(run.result.get("iterations", 0))
            failure_reason = run.result.get("failure_reason") or ("unauthorized_file_modification" if unauthorized_files else None)
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
                    "repo_path": self._display_path(case.repo_path),
                    "repo_url": case.repo_url,
                    "base_ref": case.base_ref,
                    "test_command": case.test_command or "python -m pytest -q",
                    "issue_url": case.issue_url,
                    "ground_truth_pr": case.ground_truth_pr,
                    "ground_truth_commit": case.ground_truth_commit,
                    "success": case_passed,
                    "tests_passed": success,
                    "iterations": run.result.get("iterations", 0),
                    "files_changed": changed_files,
                    "expected_changed_files": case.expected_changed_files,
                    "unauthorized_files": unauthorized_files,
                    "high_risk_intercepted": intercepted_for_case,
                    "baseline": baseline_result,
                    "failure_reason": failure_reason,
                    "failed_phase": failed_step.phase if failure_reason and failed_step else None,
                    "failed_command": failed_command.command if failure_reason and failed_command else None,
                    "failed_command_risk": failed_command.risk_level if failure_reason and failed_command else None,
                    "summary": run.summary,
                }
            )

        result = {
            "pass_rate": round(passed / len(cases), 4),
            "baseline_pass_rate": round(baseline_passed / len(cases), 4) if payload.run_baseline else None,
            "pass_rate_delta": round((passed - baseline_passed) / len(cases), 4) if payload.run_baseline else None,
            "high_risk_intercepted_count": high_risk_intercepted,
            "unauthorized_file_modification_count": unauthorized_modification_count,
            "failure_breakdown": failure_breakdown,
            "failed_phase_breakdown": failed_phase_breakdown,
            "failed_command_breakdown": failed_command_breakdown,
            "cases": results,
        }
        if payload.write_result_file:
            result["result_file"] = self._write_result_file(payload.name, result)

        evaluation = EvaluationRun(
            name=payload.name,
            status="completed",
            case_count=len(cases),
            passed_count=passed,
            avg_iterations=round(iteration_sum / len(cases)),
            result=result,
        )
        self.db.add(evaluation)
        self.db.commit()
        self.db.refresh(evaluation)
        return evaluation

    def _load_cases(self, payload: EvaluationRunRequest) -> list[BenchmarkCase]:
        if payload.cases:
            return [self._resolve_case(case) for case in payload.cases]

        if not payload.cases_path:
            default_path = (self.project_root / self.settings.benchmark_dir).resolve()
            if default_path.exists():
                return self._read_case_file(default_path / "sample_cases.json")
            return []

        path = Path(payload.cases_path)
        if not path.is_absolute():
            path = (self.project_root / path).resolve()
        return self._read_case_file(path)

    def _read_case_file(self, path: Path) -> list[BenchmarkCase]:
        if not path.exists():
            raise FileNotFoundError(f"Benchmark case file not found: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        return [self._resolve_case(BenchmarkCase(**case)) for case in payload["cases"]]

    def _resolve_case(self, case: BenchmarkCase) -> BenchmarkCase:
        if case.repo_url:
            return case
        path = Path(case.repo_path)
        if not path.is_absolute():
            case.repo_path = str((self.project_root / path).resolve())
        return case

    def _display_path(self, path_value: str) -> str:
        if not path_value:
            return ""
        path = Path(path_value)
        try:
            return path.relative_to(self.project_root).as_posix()
        except ValueError:
            return path_value

    def _count_pending_high_risk(self, run: AgentRun) -> int:
        return sum(
            1
            for event in run.command_events
            if event.risk_level == "high_risk" and event.approval_status == "pending"
        )

    def _unauthorized_files(self, changed_files: list[str], expected_changed_files: list[str]) -> list[str]:
        if not expected_changed_files:
            return []
        expected = set(expected_changed_files)
        return [path for path in changed_files if path not in expected]

    def _write_result_file(self, name: str, result: dict) -> str:
        results_dir = self.project_root / "benchmark" / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        safe_name = "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in name.lower()).strip("-")
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        path = results_dir / f"{timestamp}-{safe_name or 'benchmark'}.json"
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return path.relative_to(self.project_root).as_posix()
