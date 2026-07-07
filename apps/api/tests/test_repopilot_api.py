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
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo_path, check=True, capture_output=True)


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_run_endpoint(tmp_path: Path):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    init_repo(repo_path)

    response = client.post(
        "/api/runs",
        json={
            "repo_path": str(repo_path),
            "task_input": "Fix the failing boundary check so zero raises ValueError.",
            "base_ref": "HEAD",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["result"]["tests_passed"] is True
    assert payload["result"]["files_changed"] == ["src/calculator.py"]
    assert len(payload["steps"]) >= 4
    assert payload["command_events"]
