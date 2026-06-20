from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from safeground.adapters import MockRobotAdapter
from safeground.agents import CommandInterpreterAgent
from safeground.cli import run_command
from safeground.cv import MockCVClient
from safeground.event_store import JsonlEventStore
from safeground.mission import MissionRunner
from safeground.models import (
    ClassificationLabel,
    EventType,
    MissionState,
    RecommendedAction,
    SafeGroundConfig,
    UserIntentType,
)
from safeground.safety import SafetyGovernor


class SafeGroundP0Tests(unittest.TestCase):
    def config(self, tmpdir: str) -> SafeGroundConfig:
        return SafeGroundConfig(event_log_path=Path(tmpdir) / "events.jsonl")

    def run_mission(self, scenario: str):
        async def _run():
            with tempfile.TemporaryDirectory() as tmpdir:
                config = self.config(tmpdir)
                event_store = JsonlEventStore(config.event_log_path)
                runner = MissionRunner(
                    config,
                    MockRobotAdapter(config),
                    MockCVClient(config),
                    event_store,
                    SafetyGovernor(config, event_store),
                )
                report = await runner.run(scenario)
                return report, event_store.events, config.event_log_path.read_text(encoding="utf-8")

        return asyncio.run(_run())

    def test_valid_fixtures_reach_report(self) -> None:
        for scenario, label in [
            ("MINE", ClassificationLabel.MINE),
            ("NOT_MINE", ClassificationLabel.NOT_MINE),
            ("UNCERTAIN", ClassificationLabel.UNCERTAIN),
        ]:
            with self.subTest(scenario=scenario):
                report, events, raw_log = self.run_mission(scenario)

                self.assertEqual(report.state, MissionState.REPORT)
                self.assertIsNotNone(report.classification)
                self.assertEqual(report.classification.label, label)
                self.assertIn(EventType.FRAME_CAPTURED, [event.event_type for event in events])
                self.assertIn("MISSION_REPORTED", raw_log)

    def test_invalid_cv_response_becomes_human_review_uncertain(self) -> None:
        report, events, _ = self.run_mission("INVALID")

        self.assertEqual(report.state, MissionState.REPORT)
        self.assertIsNotNone(report.classification)
        self.assertEqual(report.classification.label, ClassificationLabel.UNCERTAIN)
        self.assertEqual(report.recommendation, RecommendedAction.HUMAN_REVIEW)
        validated = [event for event in events if event.event_type == EventType.CV_RESULT_VALIDATED]
        self.assertFalse(validated[-1].data["valid"])
        self.assertTrue(validated[-1].data["validation_errors"])

    def test_low_confidence_is_normalized_to_uncertain(self) -> None:
        report, _, _ = self.run_mission("LOW_CONFIDENCE")

        self.assertIsNotNone(report.classification)
        self.assertEqual(report.classification.label, ClassificationLabel.UNCERTAIN)
        self.assertEqual(report.recommendation, RecommendedAction.HUMAN_REVIEW)

    def test_unsafe_action_is_rejected_before_adapter_call(self) -> None:
        async def _run():
            with tempfile.TemporaryDirectory() as tmpdir:
                config = self.config(tmpdir)
                event_store = JsonlEventStore(config.event_log_path)
                safety = SafetyGovernor(config, event_store)
                mission = MissionRunner(
                    config,
                    MockRobotAdapter(config),
                    MockCVClient(config),
                    event_store,
                    safety,
                ).mission

                async def unsafe_operation():
                    raise AssertionError("unsafe operation should not run")

                with self.assertRaises(PermissionError):
                    await safety.run_checked(mission, "touch_target", unsafe_operation)

                self.assertEqual(event_store.events[-1].event_type, EventType.SAFETY_CHECK_FAILED)

        asyncio.run(_run())

    def test_chat_command_runs_mock_mission(self) -> None:
        async def _run():
            with tempfile.TemporaryDirectory() as tmpdir:
                config = self.config(tmpdir)
                report, events = await run_command(
                    config,
                    "ispeziona settore B2 con scenario dubbio",
                    "MINE",
                )
                return report, events.events

        report, events = asyncio.run(_run())

        self.assertEqual(report.state, MissionState.REPORT)
        self.assertIsNotNone(report.classification)
        self.assertEqual(report.classification.label, ClassificationLabel.UNCERTAIN)
        event_types = [event.event_type for event in events]
        self.assertIn(EventType.AGENT_INTENT_PARSED, event_types)
        self.assertIn(EventType.AGENT_DECISION_MADE, event_types)

    def test_stop_command_bypasses_mission_run(self) -> None:
        async def _run():
            with tempfile.TemporaryDirectory() as tmpdir:
                config = self.config(tmpdir)
                report, events = await run_command(config, "ferma tutto subito", "MINE")
                return report, events.events

        report, events = asyncio.run(_run())

        self.assertEqual(report.state, MissionState.MANUAL_STOP)
        self.assertIsNone(report.classification)
        self.assertIn(EventType.MISSION_STOPPED, [event.event_type for event in events])

    def test_unknown_command_requires_human_review(self) -> None:
        intent = CommandInterpreterAgent().parse("raccontami una barzelletta")

        self.assertEqual(intent.intent, UserIntentType.UNKNOWN)


if __name__ == "__main__":
    unittest.main()
