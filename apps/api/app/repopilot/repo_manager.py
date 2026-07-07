import shutil
import subprocess
from pathlib import Path

from app.core.config import get_settings


class RepoManager:
    def __init__(self) -> None:
        self.settings = get_settings()

    def ensure_repo(self, repo_path: str) -> Path:
        path = Path(repo_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Repository path does not exist: {repo_path}")
        if not (path / ".git").exists():
            raise ValueError(f"Repository path is not a git repository: {repo_path}")
        return path

    def create_worktree(self, repo_path: Path, run_id: str, base_ref: str) -> Path:
        worktree_root = self.settings.worktree_base_dir.resolve()
        worktree_root.mkdir(parents=True, exist_ok=True)
        worktree_path = worktree_root / run_id
        if worktree_path.exists():
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(worktree_path)],
                cwd=repo_path,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if worktree_path.exists():
                shutil.rmtree(worktree_path)
        subprocess.run(
            ["git", "worktree", "prune"],
            cwd=repo_path,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        subprocess.run(
            ["git", "worktree", "add", "--detach", str(worktree_path), base_ref],
            cwd=repo_path,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return worktree_path
