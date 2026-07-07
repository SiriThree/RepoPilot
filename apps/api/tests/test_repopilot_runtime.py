import subprocess
from pathlib import Path

import pytest

from app.db.models import AgentRun
from app.db.session import SessionLocal
from app.repopilot.runtime import RepoPilotRuntime
from app.schemas.repopilot import AgentRunRequest


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
async def test_runtime_executes_repair_loop(tmp_path: Path):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    init_repo(repo_path)

    db = SessionLocal()
    try:
        runtime = RepoPilotRuntime(db)
        run = await runtime.create_and_execute(
            AgentRunRequest(
                repo_path=str(repo_path),
                task_input="Fix the failing boundary check so zero raises ValueError.",
                base_ref="HEAD",
            )
        )

        saved_run = db.get(AgentRun, run.id)
        assert saved_run is not None
        assert saved_run.status == "completed"
        assert saved_run.result["tests_passed"] is True
        assert any(step.tool_name == "run_tests" for step in saved_run.steps)
        assert any("pytest" in event.command for event in saved_run.command_events)
    finally:
        db.close()
