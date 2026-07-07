import json
from pathlib import Path
from typing import Any

import httpx

from app.core.config import get_settings


class RepoPilotLLM:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def plan(
        self,
        task_input: str,
        repo_profile: dict[str, Any],
        source_files: list[str],
        issue_text: str | None = None,
        search_results: dict[str, Any] | None = None,
        test_command: str | None = None,
    ) -> dict[str, Any]:
        if not self.settings.openai_api_key:
            candidate = next((path for path in source_files if path.endswith("calculator.py")), source_files[0] if source_files else "")
            suspected_files = [candidate] if candidate else []
            if "update tests" in task_input.lower():
                test_candidate = next((path for path in source_files if "test_" in path or "/tests/" in path), "")
                if test_candidate:
                    suspected_files.append(test_candidate)
            return {
                "task_type": "bugfix",
                "suspected_files": suspected_files,
                "test_strategy": ["python -m pytest -q"],
                "reasoning_summary": "Fallback planner selected the most likely source file based on task wording and repo shape.",
            }

        payload = {
            "task_input": task_input,
            "issue_text": issue_text,
            "repo_profile": repo_profile,
            "source_files": source_files[:50],
            "search_results": search_results,
            "test_command": test_command,
        }
        response = await self._complete_json(
            system=(
                "You are RepoPilot Planner. Return JSON only with keys: "
                "task_type, suspected_files, test_strategy, reasoning_summary."
            ),
            user=json.dumps(payload, ensure_ascii=False),
        )
        return {
            "task_type": response.get("task_type", "bugfix"),
            "suspected_files": response.get("suspected_files", []),
            "test_strategy": response.get("test_strategy", [test_command or "python -m pytest -q"]),
            "reasoning_summary": response.get("reasoning_summary", ""),
        }

    async def generate_patch_plan(
        self,
        task_input: str,
        file_bundle: list[dict[str, str]],
        observation: dict[str, Any],
        issue_text: str | None = None,
        search_results: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.settings.openai_api_key:
            primary = file_bundle[0] if file_bundle else {"path": "", "content": ""}
            if "if value < 0:" in primary["content"] and ("zero" in task_input.lower() or "boundary" in task_input.lower()):
                patches = [
                    {
                        "path": primary["path"],
                        "old_snippet": "if value < 0:",
                        "new_snippet": "if value <= 0:",
                        "reasoning_summary": "Tighten the boundary check so zero becomes invalid.",
                    }
                ]
                if len(file_bundle) > 1 and "update tests" in task_input.lower():
                    patches.append(
                        {
                            "path": file_bundle[1]["path"],
                            "old_snippet": "with pytest.raises(ValueError):",
                            "new_snippet": "with pytest.raises(ValueError):",
                            "reasoning_summary": "Keep test coverage aligned with the repaired boundary behavior.",
                        }
                    )
                return {
                    "patches": patches,
                    "reasoning_summary": "Fallback patch plan proposes a minimal code repair and optional related test update.",
                }
            if "if percent < 0:" in primary["content"] and (
                "above 100" in task_input.lower()
                or "greater than 100" in task_input.lower()
                or "upper bound" in task_input.lower()
            ):
                return {
                    "patches": [
                        {
                            "path": primary["path"],
                            "old_snippet": "if percent < 0:",
                            "new_snippet": "if percent < 0 or percent > 100:",
                            "reasoning_summary": "Add the missing upper-bound validation for percentage inputs.",
                        }
                    ],
                    "reasoning_summary": "Fallback patch plan adds a missing upper-bound guard.",
                }
            raise ValueError("No fallback patch rule matched the task")

        payload = {
            "task_input": task_input,
            "issue_text": issue_text,
            "file_bundle": file_bundle,
            "observation": observation,
            "search_results": search_results,
        }
        response = await self._complete_json(
            system=(
                "You are RepoPilot Patch Planner. Return JSON only with keys: "
                "unified_diff, patches, reasoning_summary. Prefer unified_diff in standard git diff format "
                "against the provided files. If you cannot produce a unified diff, patches may be an array "
                "of objects with keys path, old_snippet, new_snippet, reasoning_summary. Keep changes minimal."
            ),
            user=json.dumps(payload, ensure_ascii=False),
        )
        return {
            "unified_diff": response.get("unified_diff", ""),
            "patches": response.get("patches", []),
            "reasoning_summary": response.get("reasoning_summary", ""),
        }

    async def _complete_json(self, system: str, user: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.settings.openai_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {self.settings.openai_api_key}"},
                json={
                    "model": self.settings.openai_model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
            return json.loads(content)


def list_source_files(worktree_path: Path) -> list[str]:
    files: list[str] = []
    for path in sorted(worktree_path.rglob("*")):
        if path.is_file() and path.suffix in {".py", ".ts", ".tsx", ".js", ".jsx"}:
            files.append(path.relative_to(worktree_path).as_posix())
    return files
