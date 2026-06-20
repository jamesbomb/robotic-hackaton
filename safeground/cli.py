from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from safeground.agents import CommandInterpreterAgent, OrchestratorAgent
from safeground.adapters import build_mock_fleet
from safeground.cv import SCENARIO_TO_FIXTURE, MockCVClient
from safeground.event_store import JsonlEventStore
from safeground.mission import MissionRunner
from safeground.models import AgentDecisionType, EventType, MissionReport, SafeGroundConfig
from safeground.safety import SafetyGovernor
from safeground.voice.whisper import transcribe_audio_file


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
    parser.add_argument(
        "--command",
        help="Chat-style operator command, e.g. 'ispeziona settore B2' or 'ferma tutto'.",
    )
    parser.add_argument(
        "--voice-wav",
        type=Path,
        help="Optional WAV/audio file transcribed with Whisper, then handled like --command.",
    )
    parser.add_argument(
        "--whisper-model",
        default="tiny",
        help="Whisper model name for --voice-wav (requires optional whisper package).",
    )
    parser.add_argument(
        "--route-over-mine",
        action="store_true",
        help="Demo flag: mark the primary route as crossing the detected mine.",
    )
    return parser


async def run_one(config: SafeGroundConfig, scenario: str) -> tuple[MissionReport, JsonlEventStore]:
    event_store = JsonlEventStore(config.event_log_path)
    fleet = build_mock_fleet(config)
    robot = fleet.get(config.robot_id) or fleet["go2"]
    cv_client = MockCVClient(config)
    safety = SafetyGovernor(config, event_store)
    runner = MissionRunner(config, robot, cv_client, event_store, safety, fleet=fleet)
    report = await runner.run(scenario)
    return report, event_store


async def main_async(args: argparse.Namespace) -> int:
    command_text = args.command
    if args.voice_wav:
        command_text = transcribe_audio_file(args.voice_wav, model_name=args.whisper_model)

    if command_text:
        config = SafeGroundConfig(
            event_log_path=args.event_log,
            route_over_mine=args.route_over_mine,
        )
        report, event_store = await run_command(config, command_text, args.scenario)
        print(json.dumps(report.model_dump(mode="json"), indent=2))
        print(f"event_log={args.event_log}")
        if args.print_events:
            for event in event_store.events:
                print(json.dumps(event.model_dump(mode="json"), ensure_ascii=True))
        return 0

    scenarios = DEMO_SCENARIOS if args.scenario == "ALL" else [args.scenario]
    reports: list[MissionReport] = []
    all_events = []

    for scenario in scenarios:
        config = SafeGroundConfig(
            event_log_path=args.event_log,
            route_over_mine=args.route_over_mine,
        )
        report, event_store = await run_one(config, scenario)
        reports.append(report)
        all_events.extend(event_store.events)

    print(json.dumps([report.model_dump(mode="json") for report in reports], indent=2))
    print(f"event_log={args.event_log}")

    if args.print_events:
        for event in all_events:
            print(json.dumps(event.model_dump(mode="json"), ensure_ascii=True))

    return 0


async def run_command(
    config: SafeGroundConfig,
    command_text: str,
    fallback_scenario: str,
) -> tuple[MissionReport, JsonlEventStore]:
    event_store = JsonlEventStore(config.event_log_path)
    fleet = build_mock_fleet(config)
    robot = fleet.get(config.robot_id) or fleet["go2"]
    cv_client = MockCVClient(config)
    safety = SafetyGovernor(config, event_store)
    runner = MissionRunner(config, robot, cv_client, event_store, safety, fleet=fleet)

    event_store.emit(
        runner.mission.mission_id,
        EventType.USER_COMMAND_RECEIVED,
        state=runner.mission.state,
        robot_id=robot.id,
        data={"text": command_text},
    )
    intent = CommandInterpreterAgent().parse(command_text)
    event_store.emit(
        runner.mission.mission_id,
        EventType.AGENT_INTENT_PARSED,
        state=runner.mission.state,
        robot_id=robot.id,
        data=intent.model_dump(mode="json"),
    )
    decision = OrchestratorAgent(config).decide(intent)
    event_store.emit(
        runner.mission.mission_id,
        EventType.AGENT_DECISION_MADE,
        state=runner.mission.state,
        robot_id=robot.id,
        data=decision.model_dump(mode="json"),
    )

    if decision.decision == AgentDecisionType.STOP_ALL:
        return await runner.stop(), event_store

    if decision.decision == AgentDecisionType.REPORT_STATUS:
        await runner._record_robot_status()
        report = runner._build_report(summary="Status reported; no mission was started.")
        return report, event_store

    if decision.decision == AgentDecisionType.RUN_MISSION:
        scenario = decision.scenario_hint or fallback_scenario
        if scenario == "ALL":
            scenario = "MINE"
        report = await runner.run(scenario, target_sector=decision.target_sector)
        return report, event_store

    report = runner._build_report(summary="Command requires human review; no mission was started.")
    return report, event_store


def main() -> int:
    return asyncio.run(main_async(build_parser().parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
