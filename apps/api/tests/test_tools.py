import subprocess
from pathlib import Path

from app.repopilot.tools import RepoTools


def init_repo(repo_path: Path) -> None:
    (repo_path / "src").mkdir()
    (repo_path / "src" / "calculator.py").write_text(
        "def normalize(value: int) -> int:\n"
        "    if value < 0:\n"
        "        raise ValueError('value must be positive')\n"
        "    return value\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo_path, check=True, capture_output=True)


def test_apply_unified_diff_uses_git_apply(tmp_path: Path):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    init_repo(repo_path)

    diff = """diff --git a/src/calculator.py b/src/calculator.py
--- a/src/calculator.py
+++ b/src/calculator.py
@@ -1,4 +1,4 @@
 def normalize(value: int) -> int:
-    if value < 0:
+    if value <= 0:
         raise ValueError('value must be positive')
     return value
"""

    result = RepoTools().apply_unified_diff(repo_path, diff)
    assert result["risk_level"] == "guarded_write"
    assert "if value <= 0:" in (repo_path / "src" / "calculator.py").read_text(encoding="utf-8")
