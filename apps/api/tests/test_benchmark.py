import subprocess
from pathlib import Path

import pytest

from app.db.session import SessionLocal
from app.repopilot.benchmark import BenchmarkRunner
from app.schemas.repopilot import EvaluationRunRequest


def init_repo(repo_path: Path) -> None:
    (repo_path / "src").mkdir()
    (repo_path / "tests").mkdir()
    (repo_path / "src" / "__init__.py").write_text("", encoding="utf-8")
    (repo_path / "src" / "calculator.py").write_text(
        "def normalize(value: int) -> int:\n"
        "    if value < 0:\n"
        "        raise ValueError('value must be positive')\n"
        "    return value\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "test_calculator.py").write_text(
        "import pytest\n"
        "from src.calculator import normalize\n\n"
        "def test_zero_is_invalid():\n"
        "    with pytest.raises(ValueError):\n"
        "        normalize(0)\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo_path, check=True, capture_output=True)


@pytest.mark.asyncio
async def test_benchmark_runner_executes_cases(tmp_path: Path):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    init_repo(repo_path)

    db = SessionLocal()
    try:
        runner = BenchmarkRunner(db)
        evaluation = await runner.create_and_execute(
            EvaluationRunRequest(
                name="sample-benchmark",
                cases=[
                    {
                        "name": "zero-boundary-fix",
                        "repo_path": str(repo_path),
                        "task_input": "Fix the failing boundary check so zero raises ValueError.",
                        "base_ref": "HEAD",
                        "expected_changed_files": ["src/calculator.py"],
                    }
                ],
            )
        )
        assert evaluation.case_count == 1
        assert evaluation.passed_count == 1
        assert evaluation.result["cases"][0]["success"] is True
    finally:
        db.close()
