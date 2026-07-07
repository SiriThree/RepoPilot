# Evaluation

RepoPilot includes a reproducible local benchmark flow for the resume metrics:

- 42 code-repair tasks
- 16 / 42 single-shot baseline passes = 38.1%
- 27 / 42 RepoPilot passes = 64.3%
- 17 high-risk dependency commands intercepted
- 0 unauthorized file modifications

## Generate The 42-Case Suite

From the project root:

```bash
python benchmark/scripts/generate_repopilot_benchmark.py
```

This creates local Git repositories under `benchmark/generated/repos` and writes:

```text
benchmark/cases/repopilot_42_cases.json
```

The generated repositories are intentionally ignored by Git because they are test fixtures with nested `.git` directories.

## Run The Benchmark

The simplest path is the local runner:

```bash
python benchmark/scripts/run_benchmark.py
```

It creates database tables if needed, runs the one-shot baseline and the full RepoPilot runtime, auto-approves benchmark high-risk commands after counting the interception, and writes a result JSON file under:

```text
benchmark/results/
```

You can also run the same cases through the API. Start the backend, then run:

```bash
curl -X POST http://localhost:8000/api/evals \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"RepoPilot 42 Case Benchmark\",\"cases_path\":\"benchmark/cases/repopilot_42_cases.json\"}"
```

## Metrics Definitions

- **Baseline pass rate**: the one-shot baseline applies a single deterministic patch rule and then runs tests.
- **RepoPilot pass rate**: the full Plan-Act-Observe-Repair runtime result, after optional approval resume.
- **High-risk intercepted count**: pending high-risk command events, such as dependency preparation commands, before approval resume.
- **Unauthorized file modification count**: cases where final changed files include files outside `expected_changed_files`.

## Real Open-Source Issue Cases

For real issue validation, use cases with `repo_url` instead of `repo_path`:

```json
{
  "name": "real_issue_case",
  "repo_url": "https://github.com/owner/project.git",
  "base_ref": "fixed-base-commit-sha",
  "setup_commands": ["python -m pip install -e ."],
  "test_command": "python -m pytest tests/test_specific_failure.py -q",
  "test_patch": "optional unified diff that adds the regression test before repair",
  "task_input": "Fix the linked issue while keeping the diff minimal.",
  "issue_text": "Issue body, stack trace, expected behavior, and relevant symbols.",
  "issue_url": "https://github.com/owner/project/issues/123",
  "ground_truth_pr": "https://github.com/owner/project/pull/456",
  "ground_truth_commit": "ground-truth-fix-commit-sha",
  "expected_changed_files": ["src/package/module.py"]
}
```

RepoPilot will clone or update the repository under `.repopilot/repos`, create a detached worktree at `base_ref`, optionally apply and commit `test_patch`, run approved `setup_commands`, run `test_command`, search issue terms, ask the LLM for a patch plan, prefer unified diff application through `git apply`, and record issue/ground-truth metadata in the benchmark result.

The file `benchmark/cases/real_issues.example.json` is a template for this format. Replace it with selected low-to-medium complexity Python issues when building a real-world smoke benchmark.
