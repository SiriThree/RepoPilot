import os
import re
import shlex
import shutil
import subprocess
import time
from pathlib import Path


class CommandRunner:
    SAFE_READ = {"git", "rg"}
    SAFE_EXEC = {"pytest", "python"}
    HIGH_RISK = {"pip", "npm"}

    def classify(self, command: list[str]) -> str:
        if not command:
            return "blocked"
        head = command[0]
        if head == "git" and len(command) > 1 and command[1] == "apply":
            return "guarded_write"
        if head == "python" and len(command) > 2 and command[1] == "-m" and command[2] == "pip":
            return "high_risk"
        if head == "git" and len(command) > 1 and command[1] not in {"diff", "status", "show", "ls-files", "grep"}:
            return "blocked"
        if head in self.SAFE_READ:
            return "safe_read"
        if head in self.SAFE_EXEC:
            return "safe_exec"
        if head in self.HIGH_RISK:
            return "high_risk"
        return "blocked"

    def run(
        self,
        command: list[str],
        cwd: Path,
        extra_env: dict[str, str] | None = None,
        approved_commands: set[str] | None = None,
        command_key: str | None = None,
    ) -> dict:
        risk = self.classify(command)
        command_key = command_key or " ".join(command)
        approved_commands = approved_commands or set()
        if risk == "blocked":
            raise ValueError(f"Blocked command: {' '.join(command)}")
        if risk == "high_risk" and command_key not in approved_commands:
            return {
                "command": " ".join(command),
                "command_key": command_key,
                "risk_level": risk,
                "approval_status": "pending",
                "exit_code": None,
                "stdout": "",
                "stderr": "",
                "duration_ms": 0,
            }

        start = time.perf_counter()
        env = os.environ.copy()
        if extra_env:
            env.update(extra_env)
        completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True, env=env, encoding="utf-8", errors="replace")
        duration_ms = int((time.perf_counter() - start) * 1000)
        return {
            "command": " ".join(command),
            "command_key": command_key,
            "risk_level": risk,
            "approval_status": "approved" if risk == "high_risk" else "auto_approved",
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "duration_ms": duration_ms,
        }


class RepoTools:
    def __init__(self) -> None:
        self.runner = CommandRunner()

    def repo_profile(self, repo_path: Path) -> dict:
        files = list(repo_path.rglob("*"))
        source_files = [path for path in files if path.is_file()]
        languages = set()
        for path in source_files:
            if path.suffix == ".py":
                languages.add("python")
            elif path.suffix in {".ts", ".tsx", ".js", ".jsx"}:
                languages.add("typescript_or_javascript")
        return {
            "file_count": len(source_files),
            "languages": sorted(languages),
            "has_pytest": any(path.name.startswith("test_") and path.suffix == ".py" for path in source_files),
            "top_level_dirs": sorted([path.name for path in repo_path.iterdir() if path.is_dir() and path.name != ".git"]),
        }

    def search_code(self, repo_path: Path, query: str) -> dict:
        rg_path = shutil.which("rg")
        if rg_path:
            result = self.runner.run(["rg", "-n", query, "."], cwd=repo_path)
            matches = result["stdout"].splitlines()[:20]
            return {"matches": matches, "command_event": result}

        matches: list[str] = []
        for path in repo_path.rglob("*.py"):
            for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if query in line:
                    matches.append(f"{path.relative_to(repo_path).as_posix()}:{index}:{line.strip()}")
                    if len(matches) >= 20:
                        break
        return {"matches": matches, "command_event": None}

    def search_issue_terms(self, repo_path: Path, text: str, limit: int = 5) -> dict:
        terms = self.extract_search_terms(text)
        searches = []
        for term in terms[:limit]:
            result = self.search_code(repo_path, term)
            searches.append({"term": term, "matches": result["matches"][:10]})
        return {"terms": terms[:limit], "searches": searches}

    def extract_search_terms(self, text: str) -> list[str]:
        quoted = re.findall(r"`([^`]+)`", text)
        identifiers = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]{2,}\b", text)
        stop_words = {
            "the", "and", "for", "with", "that", "this", "then", "into", "from", "when",
            "where", "issue", "fix", "failing", "failure", "error", "test", "tests",
            "should", "raises", "value", "return", "install", "dependencies", "needed",
        }
        terms: list[str] = []
        for term in quoted + identifiers:
            lowered = term.lower()
            if lowered in stop_words or len(term) < 3:
                continue
            if term not in terms:
                terms.append(term)
        return terms

    def read_file(self, repo_path: Path, relative_path: str) -> dict:
        path = (repo_path / relative_path).resolve()
        if repo_path.resolve() not in path.parents and path != repo_path.resolve():
            raise ValueError("Attempted to read file outside worktree")
        content = path.read_text(encoding="utf-8")
        return {"path": Path(relative_path).as_posix(), "content": content}

    def apply_patch(self, repo_path: Path, relative_path: str, old: str, new: str) -> dict:
        path = repo_path / relative_path
        content = path.read_text(encoding="utf-8")
        if old not in content:
            raise ValueError(f"Patch target not found in {relative_path}")
        updated = content.replace(old, new, 1)
        path.write_text(updated, encoding="utf-8")
        return {"path": Path(relative_path).as_posix(), "updated": True}

    def apply_unified_diff(self, repo_path: Path, unified_diff: str) -> dict:
        if not unified_diff.strip():
            raise ValueError("Unified diff is empty")
        start = time.perf_counter()
        completed = subprocess.run(
            ["git", "apply", "--recount", "--whitespace=nowarn", "-"],
            cwd=repo_path,
            input=unified_diff,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        duration_ms = int((time.perf_counter() - start) * 1000)
        if completed.returncode != 0:
            raise ValueError(f"git apply failed: {completed.stderr.strip() or completed.stdout.strip()}")
        return {
            "command": "git apply --recount --whitespace=nowarn -",
            "risk_level": "guarded_write",
            "approval_status": "auto_approved",
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "duration_ms": duration_ms,
        }

    def run_tests(self, repo_path: Path, test_command: str | None = None) -> dict:
        python_path = str(repo_path)
        existing = os.environ.get("PYTHONPATH", "")
        merged = python_path if not existing else os.pathsep.join([python_path, existing])
        command = self._parse_test_command(test_command or "python -m pytest -q")
        return self.runner.run(command, cwd=repo_path, extra_env={"PYTHONPATH": merged})

    def _parse_test_command(self, test_command: str) -> list[str]:
        try:
            return shlex.split(test_command, posix=os.name != "nt")
        except ValueError as exc:
            raise ValueError(f"Invalid test command: {test_command}") from exc

    def git_diff(self, repo_path: Path) -> dict:
        return self.runner.run(["git", "diff", "--", "."], cwd=repo_path)

    def install_dependencies(self, repo_path: Path, approved_commands: set[str]) -> dict | None:
        requirements = repo_path / "requirements.txt"
        package_json = repo_path / "package.json"
        if requirements.exists():
            return self.runner.run(
                ["python", "-m", "pip", "--version"],
                cwd=repo_path,
                approved_commands=approved_commands,
            )
        if package_json.exists():
            return self.runner.run(
                ["npm", "--version"],
                cwd=repo_path,
                approved_commands=approved_commands,
            )
        return None
