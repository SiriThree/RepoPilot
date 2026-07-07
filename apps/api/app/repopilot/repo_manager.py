import shutil
import subprocess
import hashlib
from pathlib import Path

from app.core.config import get_settings


class RepoManager:
    def __init__(self) -> None:
        self.settings = get_settings()

    def prepare_repo(self, repo_path: str = "", repo_url: str | None = None) -> Path:
        if repo_url:
            return self.clone_or_update(repo_url)
        if not repo_path:
            raise ValueError("Either repo_path or repo_url is required")
        return self.ensure_repo(repo_path)

    def ensure_repo(self, repo_path: str) -> Path:
        path = Path(repo_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Repository path does not exist: {repo_path}")
        if not (path / ".git").exists():
            raise ValueError(f"Repository path is not a git repository: {repo_path}")
        return path

    def clone_or_update(self, repo_url: str) -> Path:
        clone_root = self.settings.clone_base_dir.resolve()
        clone_root.mkdir(parents=True, exist_ok=True)
        repo_name = repo_url.rstrip("/").removesuffix(".git").split("/")[-1] or "repo"
        digest = hashlib.sha1(repo_url.encode("utf-8")).hexdigest()[:10]
        repo_path = clone_root / f"{repo_name}-{digest}"
        if not repo_path.exists():
            subprocess.run(
                ["git", "clone", repo_url, str(repo_path)],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        else:
            subprocess.run(
                ["git", "fetch", "--all", "--tags", "--prune"],
                cwd=repo_path,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        return self.ensure_repo(str(repo_path))

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
        subprocess.run(
            ["git", "checkout", "--detach", base_ref],
            cwd=worktree_path,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return worktree_path
