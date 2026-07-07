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


def init_percent_repo(repo_path: Path) -> None:
    (repo_path / "src").mkdir()
    (repo_path / "tests").mkdir()
    (repo_path / "src" / "__init__.py").write_text("", encoding="utf-8")
    (repo_path / "src" / "calculator.py").write_text(
        "def validate_percent(percent: int) -> int:\n"
        "    if percent < 0:\n"
        "        raise ValueError('percent must be between 0 and 100')\n"
        "    return percent\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "test_calculator.py").write_text(
        "import pytest\n"
        "from src.calculator import validate_percent\n\n"
        "def test_percent_above_100_is_invalid():\n"
        "    with pytest.raises(ValueError):\n"
        "        validate_percent(101)\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo_path, check=True, capture_output=True)


def init_unsupported_repo(repo_path: Path) -> None:
    (repo_path / "src").mkdir()
    (repo_path / "tests").mkdir()
    (repo_path / "src" / "__init__.py").write_text("", encoding="utf-8")
    (repo_path / "src" / "calculator.py").write_text(
        "def first_item(items: list[int]) -> int | None:\n"
        "    if not items:\n"
        "        return None\n"
        "    return items[0]\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "test_calculator.py").write_text(
        "import pytest\n"
        "from src.calculator import first_item\n\n"
        "def test_empty_list_raises_value_error():\n"
        "    with pytest.raises(ValueError):\n"
        "        first_item([])\n",
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
                write_result_file=False,
            )
        )
        assert evaluation.case_count == 1
        assert evaluation.passed_count == 1
        assert evaluation.result["cases"][0]["success"] is True
    finally:
        db.close()


@pytest.mark.asyncio
async def test_benchmark_runner_records_resume_metrics(tmp_path: Path):
    zero_repo = tmp_path / "zero"
    percent_repo = tmp_path / "percent"
    unsupported_repo = tmp_path / "unsupported"
    zero_repo.mkdir()
    percent_repo.mkdir()
    unsupported_repo.mkdir()
    init_repo(zero_repo)
    (zero_repo / "requirements.txt").write_text("pytest\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=zero_repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "add requirements"], cwd=zero_repo, check=True, capture_output=True)
    init_percent_repo(percent_repo)
    init_unsupported_repo(unsupported_repo)

    db = SessionLocal()
    try:
        runner = BenchmarkRunner(db)
        evaluation = await runner.create_and_execute(
            EvaluationRunRequest(
                name="metric-benchmark",
                write_result_file=False,
                cases=[
                    {
                        "name": "zero-boundary-high-risk",
                        "repo_path": str(zero_repo),
                        "task_input": "Install dependencies if needed, then fix the boundary check so zero raises ValueError.",
                        "expected_changed_files": ["src/calculator.py"],
                    },
                    {
                        "name": "percent-upper-bound",
                        "repo_path": str(percent_repo),
                        "task_input": "Fix the missing upper bound so percentages above 100 raise ValueError.",
                        "expected_changed_files": ["src/calculator.py"],
                    },
                    {
                        "name": "unsupported-empty-list",
                        "repo_path": str(unsupported_repo),
                        "task_input": "Fix empty list handling so first_item raises ValueError instead of returning None.",
                        "expected_changed_files": ["src/calculator.py"],
                    },
                ],
            )
        )

        assert evaluation.case_count == 3
        assert evaluation.passed_count == 2
        assert evaluation.result["baseline_pass_rate"] == 0.3333
        assert evaluation.result["pass_rate"] == 0.6667
        assert evaluation.result["high_risk_intercepted_count"] == 1
        assert evaluation.result["unauthorized_file_modification_count"] == 0
        assert evaluation.result["failure_breakdown"] == {"patch_generation_failed": 1}
    finally:
        db.close()
