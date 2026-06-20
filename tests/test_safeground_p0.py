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
    BaseMovementAction,
    BaseMovementCommand,
    ClassificationLabel,
    EventType,
    ManualArmAction,
    ManualArmCommand,
    MissionState,
    RecommendedAction,
    RouteSafetyStatus,
    SafeGroundConfig,
    UserIntentType,
)
from safeground.safety import SafetyGovernor
from safeground.services.orchestrator_service import OrchestratorService


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
            ("FIELD", ClassificationLabel.UNCERTAIN),
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
                    "ispeziona il campo con lattine arancioni nere e verdi",
                    "FIELD",
                )
                return report, events.events

        report, events = asyncio.run(_run())

        self.assertEqual(report.state, MissionState.REPORT)
        self.assertIsNotNone(report.classification)
        self.assertEqual(report.classification.label, ClassificationLabel.MINE)
        self.assertEqual(len(report.observations), 2)
        self.assertIsNotNone(report.route_trace)
        self.assertEqual(report.route_trace.status, RouteSafetyStatus.SAFE)
        event_types = [event.event_type for event in events]
        self.assertIn(EventType.AGENT_INTENT_PARSED, event_types)
        self.assertIn(EventType.AGENT_DECISION_MADE, event_types)
        self.assertIn(EventType.OBSERVATION_RECORDED, event_types)
        self.assertIn(EventType.ROUTE_REUSED_FOR_VERIFICATION, event_types)
        self.assertIn(EventType.CONSENSUS_REACHED, event_types)

    def test_uncertain_with_fleet_requests_second_observation(self) -> None:
        async def _run():
            with tempfile.TemporaryDirectory() as tmpdir:
                from safeground.adapters import build_mock_fleet

                config = self.config(tmpdir)
                event_store = JsonlEventStore(config.event_log_path)
                fleet = build_mock_fleet(config)
                runner = MissionRunner(
                    config,
                    fleet["go2"],
                    MockCVClient(config),
                    event_store,
                    SafetyGovernor(config, event_store),
                    fleet=fleet,
                )
                report = await runner.run("FIELD")
                return report, event_store.events

        report, events = asyncio.run(_run())

        self.assertEqual(report.state, MissionState.REPORT)
        self.assertIsNotNone(report.classification)
        self.assertEqual(report.classification.label, ClassificationLabel.MINE)
        self.assertEqual(report.observations[0].robot_id, "go2")
        self.assertEqual(report.observations[1].robot_id, "ugv-beast")
        self.assertIsNotNone(report.finding)
        self.assertIsNotNone(report.route_trace)
        self.assertEqual(report.route_trace.status, RouteSafetyStatus.SAFE)
        self.assertIn("ugv-beast", report.route_trace.reusable_by)
        event_types = [event.event_type for event in events]
        self.assertIn(EventType.ROUTE_RECORDED, event_types)
        self.assertIn(EventType.ROUTE_REUSED_FOR_VERIFICATION, event_types)
        self.assertIn(EventType.CONSENSUS_REACHED, event_types)

    def test_mobile_route_over_mine_is_invalidated(self) -> None:
        async def _run():
            with tempfile.TemporaryDirectory() as tmpdir:
                config = SafeGroundConfig(
                    event_log_path=Path(tmpdir) / "events.jsonl",
                    route_over_mine=True,
                )
                event_store = JsonlEventStore(config.event_log_path)
                runner = MissionRunner(
                    config,
                    MockRobotAdapter(config),
                    MockCVClient(config),
                    event_store,
                    SafetyGovernor(config, event_store),
                )
                report = await runner.run("MINE", target_sector="B2")
                return report, event_store.events

        report, events = asyncio.run(_run())

        self.assertIsNotNone(report.route_trace)
        self.assertEqual(report.route_trace.status, RouteSafetyStatus.UNSAFE)
        self.assertEqual(report.route_trace.reusable_by, [])
        self.assertIn(EventType.ROUTE_INVALIDATED, [event.event_type for event in events])

    def test_so101_route_over_mine_is_not_invalidated(self) -> None:
        async def _run():
            with tempfile.TemporaryDirectory() as tmpdir:
                config = SafeGroundConfig(
                    event_log_path=Path(tmpdir) / "events.jsonl",
                    robot_id="so101",
                    route_over_mine=True,
                )
                event_store = JsonlEventStore(config.event_log_path)
                runner = MissionRunner(
                    config,
                    MockRobotAdapter(config),
                    MockCVClient(config),
                    event_store,
                    SafetyGovernor(config, event_store),
                )
                report = await runner.run("MINE", target_sector="B2")
                return report, event_store.events

        report, events = asyncio.run(_run())

        self.assertIsNotNone(report.route_trace)
        self.assertEqual(report.route_trace.status, RouteSafetyStatus.SAFE)
        self.assertNotIn(EventType.ROUTE_INVALIDATED, [event.event_type for event in events])

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

    def test_orchestrator_service_exposes_fleet_snapshot_and_events(self) -> None:
        async def _run():
            with tempfile.TemporaryDirectory() as tmpdir:
                service = OrchestratorService(self.config(tmpdir))
                report = await service.start_mission("FIELD")
                snapshot = await service.snapshot()
                return report, snapshot

        report, snapshot = asyncio.run(_run())

        self.assertEqual(report.state, MissionState.REPORT)
        self.assertEqual(len(snapshot.robots), 4)
        self.assertEqual(len(report.observations), 2)
        self.assertTrue(snapshot.events)
        self.assertEqual(snapshot.report, report)

    def test_manual_so101_takeover_executes_bounded_nudge(self) -> None:
        async def _run():
            with tempfile.TemporaryDirectory() as tmpdir:
                service = OrchestratorService(self.config(tmpdir))
                result = await service.manual_arm_takeover(
                    "so101",
                    ManualArmCommand(
                        action=ManualArmAction.NUDGE_JOINT,
                        operator_confirmed=True,
                        joint_name="shoulder",
                        delta_degrees=2.0,
                        reason="Operator adjusts marker pose.",
                    ),
                )
                status = (await service.fleet["so101"].status()).task
                return result, status, service.events(limit=None)

        result, status, events = asyncio.run(_run())

        self.assertTrue(result.applied)
        self.assertEqual(result.robot_id, "so101")
        self.assertEqual(result.joint_positions_degrees["shoulder"], 2.0)
        self.assertEqual(status, "human_takeover")
        event_types = [event.event_type for event in events]
        self.assertIn(EventType.MANUAL_ARM_COMMAND_REQUESTED, event_types)
        self.assertIn(EventType.SAFETY_CHECK_PASSED, event_types)
        self.assertIn(EventType.MANUAL_ARM_COMMAND_APPLIED, event_types)

    def test_manual_so101_marker_requires_not_mine_target(self) -> None:
        async def _run():
            with tempfile.TemporaryDirectory() as tmpdir:
                service = OrchestratorService(self.config(tmpdir))
                with self.assertRaises(PermissionError):
                    await service.manual_arm_takeover(
                        "so101",
                        ManualArmCommand(
                            action=ManualArmAction.PLACE_SAFE_MARKER,
                            operator_confirmed=True,
                            target_label=ClassificationLabel.MINE,
                        ),
                    )
                return service.events(limit=None)

        events = asyncio.run(_run())

        self.assertIn(EventType.SAFETY_CHECK_FAILED, [event.event_type for event in events])

    def test_p0_base_movement_executes_bounded_forward_step(self) -> None:
        async def _run():
            with tempfile.TemporaryDirectory() as tmpdir:
                service = OrchestratorService(self.config(tmpdir))
                result = await service.move_robot_base(
                    "go2",
                    BaseMovementCommand(
                        action=BaseMovementAction.MOVE_FORWARD,
                        operator_confirmed=True,
                        distance_m=0.25,
                        reason="P0 smoke movement.",
                    ),
                )
                status = await service.fleet["go2"].status()
                return result, status, service.events(limit=None)

        result, status, events = asyncio.run(_run())

        self.assertTrue(result.applied)
        self.assertEqual(result.robot_id, "go2")
        self.assertAlmostEqual(result.pose.x, 0.45)
        self.assertEqual(status.task, "manual_base_movement")
        event_types = [event.event_type for event in events]
        self.assertIn(EventType.BASE_MOVEMENT_COMMAND_REQUESTED, event_types)
        self.assertIn(EventType.SAFETY_CHECK_PASSED, event_types)
        self.assertIn(EventType.BASE_MOVEMENT_COMMAND_APPLIED, event_types)

    def test_p0_base_movement_is_restricted_to_mobile_robots(self) -> None:
        async def _run():
            with tempfile.TemporaryDirectory() as tmpdir:
                service = OrchestratorService(self.config(tmpdir))
                with self.assertRaises(PermissionError):
                    await service.move_robot_base(
                        "so101",
                        BaseMovementCommand(
                            action=BaseMovementAction.MOVE_FORWARD,
                            operator_confirmed=True,
                            distance_m=0.25,
                        ),
                    )
                return service.events(limit=None)

        events = asyncio.run(_run())

        self.assertIn(EventType.SAFETY_CHECK_FAILED, [event.event_type for event in events])

    def test_fastapi_app_imports_with_registered_routes(self) -> None:
        from safeground.api.server import app

        paths = {route.path for route in app.routes}

        self.assertIn("/api/missions/start", paths)
        self.assertIn("/api/robots", paths)
        self.assertIn("/api/robots/{robot_id}/manual-arm", paths)
        self.assertIn("/api/robots/{robot_id}/move", paths)
        self.assertIn("/ws/events", paths)


if __name__ == "__main__":
    unittest.main()
