import argparse
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = PROJECT_ROOT / "benchmark" / "cases" / "real_issues.swebench_lite_dev.json"


def fetch_rows(split: str, length: int, offset: int) -> list[dict]:
    query = urlencode(
        {
            "dataset": "SWE-bench/SWE-bench_Lite",
            "config": "default",
            "split": split,
            "offset": offset,
            "length": length,
        }
    )
    url = f"https://datasets-server.huggingface.co/rows?{query}"
    with urlopen(url, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return [row["row"] for row in payload["rows"]]


def make_test_command(row: dict) -> str:
    tests = json.loads(row.get("FAIL_TO_PASS") or "[]")
    if tests:
        return "python -m pytest " + " ".join(tests[:3]) + " -q"
    return "python -m pytest -q"


def modified_source_files(patch: str) -> list[str]:
    files: list[str] = []
    for line in patch.splitlines():
        if line.startswith("diff --git"):
            parts = line.split()
            if len(parts) >= 4:
                path = parts[2].removeprefix("a/")
                if path not in files:
                    files.append(path)
    return files


def convert_row(row: dict) -> dict:
    repo = row["repo"]
    instance_id = row["instance_id"]
    pr_number = instance_id.rsplit("-", 1)[-1]
    return {
        "name": instance_id,
        "repo_url": f"https://github.com/{repo}.git",
        "base_ref": row["base_commit"],
        "test_command": make_test_command(row),
        "test_patch": row.get("test_patch") or None,
        "task_input": "Resolve the linked GitHub issue. Keep the patch minimal and make the failing regression tests pass.",
        "issue_text": row["problem_statement"],
        "issue_url": None,
        "ground_truth_pr": f"https://github.com/{repo}/pull/{pr_number}",
        "ground_truth_commit": row.get("patch", "")[:0] or None,
        "setup_commands": [],
        "expected_changed_files": modified_source_files(row.get("patch") or ""),
        "swebench": {
            "instance_id": instance_id,
            "version": row.get("version"),
            "environment_setup_commit": row.get("environment_setup_commit"),
            "fail_to_pass": json.loads(row.get("FAIL_TO_PASS") or "[]"),
            "pass_to_pass": json.loads(row.get("PASS_TO_PASS") or "[]"),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import a small real-issue benchmark from SWE-bench Lite.")
    parser.add_argument("--split", default="dev", choices=["dev", "test"])
    parser.add_argument("--length", type=int, default=5)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = fetch_rows(args.split, args.length, args.offset)
    cases = [convert_row(row) for row in rows]
    output = Path(args.output)
    if not output.is_absolute():
        output = PROJECT_ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"cases": cases}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(cases)} SWE-bench Lite cases to {output}")


if __name__ == "__main__":
    main()
