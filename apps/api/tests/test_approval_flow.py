import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


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
    (repo_path / "requirements.txt").write_text("pytest\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo_path, check=True, capture_output=True)


def test_run_enters_awaiting_approval_and_can_resume(tmp_path: Path):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    init_repo(repo_path)

    create_response = client.post(
        "/api/runs",
        json={
          "repo_path": str(repo_path),
          "task_input": "Install dependencies and fix the failing boundary check so zero raises ValueError.",
          "base_ref": "HEAD"
        }
    )

    assert create_response.status_code == 200
    payload = create_response.json()
    assert payload["status"] == "awaiting_approval"
    pending = payload["result"]["pending_approval"]
    assert pending["command"] == "python -m pip --version"

    approve_response = client.post(
        f"/api/runs/{payload['id']}/approve",
        json={"command_key": pending["command_key"]}
    )

    assert approve_response.status_code == 200
    approved_payload = approve_response.json()
    assert approved_payload["status"] == "completed"
    assert approved_payload["result"]["tests_passed"] is True
