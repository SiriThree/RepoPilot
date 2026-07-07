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
