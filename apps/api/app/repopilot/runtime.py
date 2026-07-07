from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models import AgentRun, CommandEvent, RunStep
from app.core.config import get_settings
from app.repopilot.llm import RepoPilotLLM, list_source_files
from app.repopilot.repo_manager import RepoManager
from app.repopilot.tools import RepoTools
from app.schemas.repopilot import AgentRunRequest


class RepoPilotRuntime:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.repo_manager = RepoManager()
        self.tools = RepoTools()
        self.llm = RepoPilotLLM()

    async def create_and_execute(self, payload: AgentRunRequest) -> AgentRun:
        return await self._start_run(payload)

    async def approve_and_resume(self, run: AgentRun, command_key: str) -> AgentRun:
        approved = list(set(run.result.get("approved_commands", [])) | {command_key})
        payload = AgentRunRequest(
            repo_path=run.repo_path,
            task_input=run.task_input,
            base_ref=run.base_ref,
            setup_commands=run.result.get("setup_commands", []),
            test_command=run.result.get("test_command"),
            test_patch=run.result.get("test_patch"),
            issue_text=run.result.get("issue_text"),
            issue_url=run.result.get("issue_url"),
            ground_truth_pr=run.result.get("ground_truth_pr"),
            ground_truth_commit=run.result.get("ground_truth_commit"),
            approved_commands=approved,
        )
        return await self._resume_run(run, payload)

    async def _start_run(self, payload: AgentRunRequest) -> AgentRun:
        repo_path = self.repo_manager.prepare_repo(payload.repo_path, payload.repo_url)
        run = AgentRun(
            repo_path=str(repo_path),
            task_input=payload.task_input,
            base_ref=payload.base_ref,
            status="running",
            worktree_path="",
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)

        worktree_path = self.repo_manager.create_worktree(repo_path, run.id, payload.base_ref)
        run.worktree_path = str(worktree_path)
        self.db.commit()

        return await self._execute_and_persist(run, worktree_path, payload)

    async def _resume_run(self, run: AgentRun, payload: AgentRunRequest) -> AgentRun:
        repo_path = self.repo_manager.prepare_repo(run.repo_path, payload.repo_url)
        worktree_path = self.repo_manager.create_worktree(repo_path, run.id, run.base_ref)
        run.worktree_path = str(worktree_path)
        run.status = "running"
        run.steps.clear()
        run.command_events.clear()
        self.db.commit()
        return await self._execute_and_persist(run, worktree_path, payload)

    async def _execute_and_persist(self, run: AgentRun, worktree_path: Path, payload: AgentRunRequest) -> AgentRun:
        try:
            result = await self._execute(run, worktree_path, payload, set(payload.approved_commands))
            run.status = result["status"]
            run.summary = result["summary"]
            run.result = result
            run.finished_at = datetime.now(UTC)
            self.db.commit()
            self.db.refresh(run)
            return run
        except Exception as exc:
            run.status = "failed"
            run.summary = "Run failed before producing a valid repair."
            run.result = {
                "tests_passed": False,
                "files_changed": [],
                "failure_reason": self._classify_failure(str(exc)),
                "error_message": str(exc),
            }
            run.finished_at = datetime.now(UTC)
            self.db.commit()
            self.db.refresh(run)
            return run

    async def _execute(self, run: AgentRun, worktree_path: Path, payload: AgentRunRequest, approved_commands: set[str]) -> dict:
        profile = self.tools.repo_profile(worktree_path)
        if payload.test_patch:
            test_patch_result = self.tools.apply_test_patch(worktree_path, payload.test_patch)
            self._record_command(run, test_patch_result)
            self._record_step(
                run,
                "setup",
                "apply_test_patch",
                {"has_test_patch": True},
                {"committed": test_patch_result["exit_code"] == 0},
            )
            profile = self.tools.repo_profile(worktree_path)
        setup_result = self._run_setup_commands(run, worktree_path, payload, approved_commands)
        if setup_result:
            return setup_result
        self._record_step(run, "plan", "repo_profile", {"repo_path": run.repo_path}, profile)
        issue_context = "\n\n".join(item for item in [payload.task_input, payload.issue_text or ""] if item)
        search_results = self.tools.search_issue_terms(worktree_path, issue_context)
        self._record_step(run, "plan", "search_issue_terms", {"issue_context": issue_context[:1000]}, search_results)
        plan = await self.llm.plan(
            run.task_input,
            profile,
            list_source_files(worktree_path),
            issue_text=payload.issue_text,
            search_results=search_results,
            test_command=payload.test_command,
        )
        self._record_step(run, "plan", "planner", {"task_input": run.task_input}, plan)

        environment_event = self._maybe_prepare_environment(run.task_input, worktree_path, approved_commands)
        if environment_event:
            self._record_command(run, environment_event)
            if environment_event["approval_status"] == "pending":
                self._record_step(
                    run,
                    "approval",
                    "request_high_risk_command",
                    {"task_input": run.task_input},
                    {
                        "command": environment_event["command"],
                        "command_key": environment_event["command"],
                        "reason": "Environment preparation requires explicit approval.",
                    },
                )
                return {
                    "status": "awaiting_approval",
                    "tests_passed": False,
                    "files_changed": [],
                    "iterations": 0,
                    "summary": "Run paused because RepoPilot needs approval for a high-risk command.",
                    "approved_commands": sorted(approved_commands),
                    "pending_approval": {
                        "command": environment_event["command"],
                        "command_key": environment_event["command"],
                        "risk_level": environment_event["risk_level"],
                        "reason": "Environment preparation requires explicit approval.",
                    },
                    "profile": profile,
                    "plan": plan,
                    "patch_plan": None,
                    "patch_proposal": None,
                    "initial_test": {"passed": False, "error_excerpt": "Awaiting approval before test execution.", "duration_ms": 0},
                    "final_test": {"passed": False, "error_excerpt": "Awaiting approval before test execution.", "duration_ms": 0},
                    "diff_text": "",
                    "diff_stats": {"added_lines": 0, "removed_lines": 0, "hunks": 0},
                    "failure_reason": "pending_approval",
                    **self._metadata(payload),
                }

        test_result = self.tools.run_tests(worktree_path, payload.test_command)
        self._record_command(run, test_result)
        initial_observation = self._summarize_test_result(test_result)
        self._record_step(run, "observe", "run_tests", {}, initial_observation)

        candidate_files = self._select_candidate_files(worktree_path, plan)
        self._record_step(
            run,
            "plan",
            "select_files",
            {"task_input": run.task_input},
            {"files": candidate_files, "planner_candidates": plan.get("suspected_files", [])},
        )
        file_bundle = []
        for relative_path in candidate_files:
            file_content = self.tools.read_file(worktree_path, relative_path)
            self._record_step(run, "act", "read_file", {"path": relative_path}, {"preview": file_content["content"][:240]})
            file_bundle.append({"path": relative_path, "content": file_content["content"]})

        iterations = 1
        patch_plan: dict | None = None
        if test_result["exit_code"] != 0:
            patch_plan = await self._repair_candidate(
                run.task_input,
                file_bundle,
                initial_observation,
                issue_text=payload.issue_text,
                search_results=search_results,
            )
            self._record_step(run, "repair", "patch_plan", {"files": candidate_files}, patch_plan)
            applied = []
            if patch_plan.get("unified_diff"):
                patch_result = self.tools.apply_unified_diff(worktree_path, patch_plan["unified_diff"])
                applied.append(patch_result)
                self._record_command(run, patch_result)
                self._record_step(run, "repair", "apply_unified_diff", {"format": "unified_diff"}, {"applied": True})
            else:
                for patch in patch_plan["patches"]:
                    patch_result = self.tools.apply_patch(
                        worktree_path,
                        patch["path"],
                        patch["old_snippet"],
                        patch["new_snippet"],
                    )
                    applied.append(patch_result)
                    self._record_step(run, "repair", "apply_patch", {"path": patch["path"]}, patch_result)
            iterations += 1

        second_test = self.tools.run_tests(worktree_path, payload.test_command)
        self._record_command(run, second_test)
        final_observation = self._summarize_test_result(second_test)
        self._record_step(run, "observe", "run_tests", {"iteration": 2}, final_observation)

        diff_result = self.tools.git_diff(worktree_path)
        self._record_command(run, diff_result)
        changed_files = self._extract_changed_files(diff_result["stdout"])
        diff_stats = self._build_diff_stats(diff_result["stdout"])
        self._record_step(
            run,
            "finish",
            "git_diff",
            {},
            {"files_changed": changed_files, "diff_preview": diff_result["stdout"][:400], "diff_stats": diff_stats},
        )

        return {
            "status": "completed" if second_test["exit_code"] == 0 else "failed",
            "tests_passed": second_test["exit_code"] == 0,
            "files_changed": changed_files,
            "iterations": iterations,
            "summary": self._build_summary(run.task_input, second_test["exit_code"] == 0, changed_files),
            "approved_commands": sorted(approved_commands),
            "pending_approval": None,
            "profile": profile,
            "plan": plan,
            "patch_plan": patch_plan,
            "patch_proposal": patch_plan["patches"][0] if patch_plan and patch_plan["patches"] else None,
            "initial_test": initial_observation,
            "final_test": final_observation,
            "diff_text": diff_result["stdout"],
            "diff_stats": diff_stats,
            "failure_reason": None if second_test["exit_code"] == 0 else self._classify_failure(final_observation["error_excerpt"]),
            **self._metadata(payload),
        }

    def _select_candidate_files(self, worktree_path: Path, plan: dict[str, object]) -> list[str]:
        candidates: list[str] = []
        for candidate in plan.get("suspected_files", []):
            path = worktree_path / str(candidate)
            if path.exists() and path.is_file():
                candidates.append(str(candidate))
        if candidates:
            return candidates[:3]
        source_files = sorted(worktree_path.rglob("*.py"))
        fallback = [path for path in source_files if "tests" not in path.parts and path.name != "__init__.py"]
        if not fallback:
            raise ValueError("No Python source file found for repair")
        return [str(fallback[0].relative_to(worktree_path))]

    async def _repair_candidate(
        self,
        task_input: str,
        file_bundle: list[dict[str, str]],
        observation: dict,
        issue_text: str | None = None,
        search_results: dict | None = None,
    ) -> dict:
        patch_plan = await self.llm.generate_patch_plan(
            task_input,
            file_bundle,
            observation,
            issue_text=issue_text,
            search_results=search_results,
        )
        patches = patch_plan.get("patches", [])
        if not patches and not patch_plan.get("unified_diff"):
            raise ValueError("Patch proposal is incomplete")
        return patch_plan

    def _summarize_test_result(self, command_result: dict) -> dict:
        stderr = command_result["stderr"].strip()
        stdout = command_result["stdout"].strip()
        excerpt = stderr or stdout
        return {
            "passed": command_result["exit_code"] == 0,
            "error_excerpt": excerpt[:500],
            "duration_ms": command_result["duration_ms"],
        }

    def _extract_changed_files(self, diff_text: str) -> list[str]:
        files: list[str] = []
        for line in diff_text.splitlines():
            if line.startswith("diff --git"):
                parts = line.split()
                if len(parts) >= 4:
                    files.append(parts[2].removeprefix("a/"))
        return files

    def _build_summary(self, task_input: str, passed: bool, changed_files: list[str]) -> str:
        outcome = "passed tests" if passed else "did not fully pass tests"
        file_summary = ", ".join(changed_files) if changed_files else "no files changed"
        return f"RepoPilot processed task '{task_input}', {outcome}, and touched {file_summary}."

    def _build_diff_stats(self, diff_text: str) -> dict:
        added = sum(1 for line in diff_text.splitlines() if line.startswith("+") and not line.startswith("+++"))
        removed = sum(1 for line in diff_text.splitlines() if line.startswith("-") and not line.startswith("---"))
        hunks = sum(1 for line in diff_text.splitlines() if line.startswith("@@"))
        return {"added_lines": added, "removed_lines": removed, "hunks": hunks}

    def _classify_failure(self, message: str) -> str:
        text = message.lower()
        if "pending approval" in text:
            return "pending_approval"
        if "blocked command" in text:
            return "blocked_command"
        if "no python source file" in text:
            return "missing_source_file"
        if "patch proposal is incomplete" in text or "no fallback patch rule matched" in text:
            return "patch_generation_failed"
        if "module not found" in text or "importerror" in text:
            return "test_environment_error"
        if "assert" in text or "failed" in text:
            return "tests_failed"
        return "runtime_error"

    def _maybe_prepare_environment(self, task_input: str, worktree_path: Path, approved_commands: set[str]) -> dict | None:
        keywords = ("install", "dependency", "dependencies", "requirements")
        if any(keyword in task_input.lower() for keyword in keywords):
            return self.tools.install_dependencies(worktree_path, approved_commands)
        return None

    def _run_setup_commands(
        self,
        run: AgentRun,
        worktree_path: Path,
        payload: AgentRunRequest,
        approved_commands: set[str],
    ) -> dict | None:
        for command in payload.setup_commands:
            result = self.tools.run_command(worktree_path, command, approved_commands)
            self._record_command(run, result)
            if result["approval_status"] == "pending":
                self._record_step(
                    run,
                    "approval",
                    "request_setup_command",
                    {"command": command},
                    {
                        "command": result["command"],
                        "command_key": result["command_key"],
                        "reason": "Setup command requires explicit approval.",
                    },
                )
                return {
                    "status": "awaiting_approval",
                    "tests_passed": False,
                    "files_changed": [],
                    "iterations": 0,
                    "summary": "Run paused because RepoPilot needs approval for a setup command.",
                    "approved_commands": sorted(approved_commands),
                    "pending_approval": {
                        "command": result["command"],
                        "command_key": result["command_key"],
                        "risk_level": result["risk_level"],
                        "reason": "Setup command requires explicit approval.",
                    },
                    "profile": self.tools.repo_profile(worktree_path),
                    "plan": None,
                    "patch_plan": None,
                    "patch_proposal": None,
                    "initial_test": {"passed": False, "error_excerpt": "Awaiting setup approval.", "duration_ms": 0},
                    "final_test": {"passed": False, "error_excerpt": "Awaiting setup approval.", "duration_ms": 0},
                    "diff_text": "",
                    "diff_stats": {"added_lines": 0, "removed_lines": 0, "hunks": 0},
                    "failure_reason": "pending_approval",
                    **self._metadata(payload),
                }
            if result["exit_code"] != 0:
                raise ValueError(f"Setup command failed: {command}")
        return None

    def _metadata(self, payload: AgentRunRequest) -> dict:
        return {
            "repo_url": payload.repo_url,
            "setup_commands": payload.setup_commands,
            "test_command": payload.test_command or "python -m pytest -q",
            "test_patch": payload.test_patch,
            "issue_text": payload.issue_text,
            "issue_url": payload.issue_url,
            "ground_truth_pr": payload.ground_truth_pr,
            "ground_truth_commit": payload.ground_truth_commit,
        }

    def _record_step(self, run: AgentRun, phase: str, tool_name: str, input_json: dict, output_json: dict) -> None:
        step = RunStep(
            run_id=run.id,
            step_index=len(run.steps) + 1,
            phase=phase,
            tool_name=tool_name,
            input_json=input_json,
            output_json=output_json,
            status="completed",
        )
        self.db.add(step)
        self.db.commit()
        self.db.refresh(run)

    def _record_command(self, run: AgentRun, command_result: dict) -> None:
        event = CommandEvent(
            run_id=run.id,
            command=command_result["command"],
            risk_level=command_result["risk_level"],
            approval_status=command_result["approval_status"],
            exit_code=command_result["exit_code"],
            stdout_summary=command_result["stdout"][:500],
            stderr_summary=command_result["stderr"][:500],
            duration_ms=command_result["duration_ms"],
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(run)
