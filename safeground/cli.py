from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from safeground.adapters import MockRobotAdapter
from safeground.cv import SCENARIO_TO_FIXTURE, MockCVClient
from safeground.event_store import JsonlEventStore
from safeground.mission import MissionRunner
from safeground.models import MissionReport, SafeGroundConfig
from safeground.safety import SafetyGovernor


DEMO_SCENARIOS = ["NOT_MINE", "MINE", "UNCERTAIN"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a SafeGround P0 mock mission.")
    parser.add_argument(
        "--scenario",
        choices=[*sorted(SCENARIO_TO_FIXTURE), "ALL"],
        default="MINE",
        help="Fixture-backed CV scenario to replay.",
    )
    parser.add_argument(
        "--event-log",
        type=Path,
        default=Path("safeground_runs/events.jsonl"),
        help="Append-only JSONL audit log path.",
    )
    parser.add_argument(
        "--print-events",
        action="store_true",
        help="Print events captured during this CLI run.",
    )
    return parser


async def run_one(config: SafeGroundConfig, scenario: str) -> tuple[MissionReport, JsonlEventStore]:
    event_store = JsonlEventStore(config.event_log_path)
    robot = MockRobotAdapter(config)
    cv_client = MockCVClient(config)
    safety = SafetyGovernor(config, event_store)
    runner = MissionRunner(config, robot, cv_client, event_store, safety)
    report = await runner.run(scenario)
    return report, event_store


async def main_async(args: argparse.Namespace) -> int:
    scenarios = DEMO_SCENARIOS if args.scenario == "ALL" else [args.scenario]
    reports: list[MissionReport] = []
    all_events = []

    for scenario in scenarios:
        config = SafeGroundConfig(event_log_path=args.event_log)
        report, event_store = await run_one(config, scenario)
        reports.append(report)
        all_events.extend(event_store.events)

    print(json.dumps([report.model_dump(mode="json") for report in reports], indent=2))
    print(f"event_log={args.event_log}")

    if args.print_events:
        for event in all_events:
            print(json.dumps(event.model_dump(mode="json"), ensure_ascii=True))

    return 0


def main() -> int:
    return asyncio.run(main_async(build_parser().parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
