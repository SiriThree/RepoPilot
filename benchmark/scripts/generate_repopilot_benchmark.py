import json
import os
import shutil
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
GENERATED_ROOT = PROJECT_ROOT / "benchmark" / "generated" / "repos"
CASES_PATH = PROJECT_ROOT / "benchmark" / "cases" / "repopilot_42_cases.json"


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run(command: list[str], cwd: Path) -> None:
    subprocess.run(
        command,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def init_git_repo(repo_path: Path) -> None:
    run(["git", "init"], repo_path)
    run(["git", "config", "user.email", "benchmark@example.com"], repo_path)
    run(["git", "config", "user.name", "RepoPilot Benchmark"], repo_path)
    run(["git", "add", "."], repo_path)
    run(["git", "commit", "-m", "init"], repo_path)


def create_zero_boundary_case(index: int, repo_path: Path) -> dict:
    write(repo_path / "src" / "__init__.py", "")
    write(
        repo_path / "src" / "calculator.py",
        "def normalize(value: int) -> int:\n"
        "    if value < 0:\n"
        "        raise ValueError('value must be positive')\n"
        "    return value\n",
    )
    write(
        repo_path / "tests" / "test_calculator.py",
        "import pytest\n"
        "from src.calculator import normalize\n\n"
        "def test_zero_is_invalid():\n"
        "    with pytest.raises(ValueError):\n"
        "        normalize(0)\n",
    )
    return {
        "name": f"zero_boundary_fix_{index:03d}",
        "repo_path": repo_path.relative_to(PROJECT_ROOT).as_posix(),
        "task_input": task_input(index, "Fix the failing boundary check so zero raises ValueError and keep the diff minimal."),
        "base_ref": "HEAD",
        "expected_changed_files": ["src/calculator.py"],
    }


def create_percent_upper_bound_case(index: int, repo_path: Path) -> dict:
    write(repo_path / "src" / "__init__.py", "")
    write(
        repo_path / "src" / "calculator.py",
        "def validate_percent(percent: int) -> int:\n"
        "    if percent < 0:\n"
        "        raise ValueError('percent must be between 0 and 100')\n"
        "    return percent\n",
    )
    write(
        repo_path / "tests" / "test_calculator.py",
        "import pytest\n"
        "from src.calculator import validate_percent\n\n"
        "def test_percent_above_100_is_invalid():\n"
        "    with pytest.raises(ValueError):\n"
        "        validate_percent(101)\n",
    )
    return {
        "name": f"percent_upper_bound_fix_{index:03d}",
        "repo_path": repo_path.relative_to(PROJECT_ROOT).as_posix(),
        "task_input": task_input(index, "Fix the missing upper bound so percentages above 100 raise ValueError."),
        "base_ref": "HEAD",
        "expected_changed_files": ["src/calculator.py"],
    }


def create_unsupported_case(index: int, repo_path: Path) -> dict:
    write(repo_path / "src" / "__init__.py", "")
    write(
        repo_path / "src" / "calculator.py",
        "def first_item(items: list[int]) -> int | None:\n"
        "    if not items:\n"
        "        return None\n"
        "    return items[0]\n",
    )
    write(
        repo_path / "tests" / "test_calculator.py",
        "import pytest\n"
        "from src.calculator import first_item\n\n"
        "def test_empty_list_raises_value_error():\n"
        "    with pytest.raises(ValueError):\n"
        "        first_item([])\n",
    )
    return {
        "name": f"unsupported_empty_collection_fix_{index:03d}",
        "repo_path": repo_path.relative_to(PROJECT_ROOT).as_posix(),
        "task_input": "Fix empty list handling so first_item raises ValueError instead of returning None.",
        "base_ref": "HEAD",
        "expected_changed_files": ["src/calculator.py"],
    }


def task_input(index: int, text: str) -> str:
    if index <= 17:
        return f"Install dependencies if needed, then {text}"
    return text


def add_requirements_if_needed(index: int, repo_path: Path) -> None:
    if index <= 17:
        write(repo_path / "requirements.txt", "pytest\n")


def build_cases() -> list[dict]:
    if GENERATED_ROOT.exists():
        shutil.rmtree(GENERATED_ROOT, onerror=handle_remove_readonly)
    GENERATED_ROOT.mkdir(parents=True, exist_ok=True)

    cases: list[dict] = []
    for index in range(1, 43):
        repo_path = GENERATED_ROOT / f"case_{index:03d}"
        repo_path.mkdir(parents=True)
        if index <= 16:
            case = create_zero_boundary_case(index, repo_path)
        elif index <= 27:
            case = create_percent_upper_bound_case(index, repo_path)
        else:
            case = create_unsupported_case(index, repo_path)
        add_requirements_if_needed(index, repo_path)
        init_git_repo(repo_path)
        cases.append(case)
    return cases


def handle_remove_readonly(function, path, _exc_info) -> None:
    os.chmod(path, 0o700)
    function(path)


def main() -> None:
    cases = build_cases()
    CASES_PATH.parent.mkdir(parents=True, exist_ok=True)
    CASES_PATH.write_text(json.dumps({"cases": cases}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Generated {len(cases)} benchmark repos under {GENERATED_ROOT}")
    print(f"Wrote case file to {CASES_PATH}")


if __name__ == "__main__":
    main()
