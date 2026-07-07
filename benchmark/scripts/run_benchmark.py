import argparse
import asyncio
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
API_ROOT = PROJECT_ROOT / "apps" / "api"
sys.path.insert(0, str(API_ROOT))

from app.db import models  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.repopilot.benchmark import BenchmarkRunner  # noqa: E402
from app.schemas.repopilot import EvaluationRunRequest  # noqa: E402


async def run(args: argparse.Namespace) -> None:
    models.Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        evaluation = await BenchmarkRunner(db).create_and_execute(
            EvaluationRunRequest(
                name=args.name,
                cases_path=args.cases_path,
                run_baseline=not args.skip_baseline,
                auto_approve_high_risk=not args.no_auto_approve,
                write_result_file=not args.no_result_file,
            )
        )
        summary = {
            "case_count": evaluation.case_count,
            "passed_count": evaluation.passed_count,
            "pass_rate": evaluation.result["pass_rate"],
            "baseline_pass_rate": evaluation.result.get("baseline_pass_rate"),
            "pass_rate_delta": evaluation.result.get("pass_rate_delta"),
            "high_risk_intercepted_count": evaluation.result["high_risk_intercepted_count"],
            "unauthorized_file_modification_count": evaluation.result["unauthorized_file_modification_count"],
            "result_file": evaluation.result.get("result_file"),
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    finally:
        db.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RepoPilot benchmark cases.")
    parser.add_argument("--cases-path", default="benchmark/cases/repopilot_42_cases.json")
    parser.add_argument("--name", default="RepoPilot 42 Case Benchmark")
    parser.add_argument("--skip-baseline", action="store_true")
    parser.add_argument("--no-auto-approve", action="store_true")
    parser.add_argument("--no-result-file", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
