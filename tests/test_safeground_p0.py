from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from safeground.adapters import MockRobotAdapter
from safeground.agents import CommandInterpreterAgent
from safeground.cli import run_command
from safeground.cyberwave_replay import replay_cyberwave_recording
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
    MapPoint,
    MissionState,
    MovementTarget,
    ObjectMarkRequest,
    ObjectPickupFinishRequest,
    ObjectPickupReplayRequest,
    ObjectPickupStartRequest,
    RecommendedAction,
    RobotActivationMode,
    RobotActivationRequest,
    RouteSafetyStatus,
    RuntimeConfigRequest,
    RuntimeMode,
    SafeGroundConfig,
    ScoutRouteCommand,
    UserIntentType,
)
from safeground.safety import SafetyGovernor
from safeground.services.orchestrator_service import OrchestratorService


class FakeMqttPublisher:
    def __init__(self) -> None:
        self.messages: list[tuple[str, dict]] = []

    def publish(self, topic: str, payload: dict) -> None:
        self.messages.append((topic, payload))


class FakeReplayResult:
    samples_published = 3


class SafeGroundP0Tests(unittest.TestCase):
    def config(self, tmpdir: str) -> SafeGroundConfig:
        return SafeGroundConfig(event_log_path=Path(tmpdir) / "events.jsonl")

    def cyberwave_config(self, tmpdir: str) -> SafeGroundConfig:
        cyberwave_dir = Path(tmpdir) / "cyberwave"
        cyberwave_dir.mkdir()
        go2_uuid = "758bee49-6668-4733-80f8-da1c0a7134b2"
        ugv_uuid = "8a40ed9f-349c-44d2-98c0-3a2282134839"
        (cyberwave_dir / "environment.json").write_text(
            json.dumps({"name": "Default Environment", "twin_uuids": [go2_uuid, ugv_uuid]}),
            encoding="utf-8",
        )
        (cyberwave_dir / f"{go2_uuid}.json").write_text(
            json.dumps(
                {
                    "uuid": go2_uuid,
                    "name": "Unitree Go2",
                    "asset": {
                        "registry_id": "unitree/go2",
                        "slug": "unitree/catalog/go2",
                        "metadata": {
                            "mqtt": {
                                "commands": {
                                    "supported": ["move_forward", "move_backward", "stop"]
                                }
                            }
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        (cyberwave_dir / f"{ugv_uuid}.json").write_text(
            json.dumps(
                {
                    "uuid": ugv_uuid,
                    "name": "UGV Beast",
                    "asset": {
                        "registry_id": "waveshare/ugv-beast",
                        "slug": "cyberwave/catalog/ugv-beast",
                        "metadata": {"mqtt": {"commands": {"supported": ["move_forward"]}}},
                    },
                }
            ),
            encoding="utf-8",
        )
        (cyberwave_dir / "camera_streams.json").write_text(
            json.dumps({"twin_to_stream_url": {go2_uuid: "http://host.docker.internal:8091"}}),
            encoding="utf-8",
        )
        return SafeGroundConfig(
            event_log_path=Path(tmpdir) / "events.jsonl",
            cyberwave_config_dir=cyberwave_dir,
            cyberwave_virtual_sync=False,
        )

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
                    "ispeziona il campo in cerca di mine",
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

    def test_runtime_update_requires_confirmation_for_live_non_dry_run(self) -> None:
        async def _run():
            with tempfile.TemporaryDirectory() as tmpdir:
                service = OrchestratorService(self.config(tmpdir))
                with self.assertRaises(PermissionError):
                    await service.update_runtime(
                        RuntimeConfigRequest(
                            runtime_mode=RuntimeMode.LIVE,
                            dry_run=False,
                            operator_confirmed=False,
                        )
                    )
                return service.events(limit=None)

        events = asyncio.run(_run())

        self.assertEqual(events, [])

    def test_runtime_update_is_reflected_in_snapshot_and_robot_status(self) -> None:
        async def _run():
            with tempfile.TemporaryDirectory() as tmpdir:
                service = OrchestratorService(self.config(tmpdir))
                status = await service.update_runtime(
                    RuntimeConfigRequest(
                        runtime_mode=RuntimeMode.LIVE,
                        dry_run=False,
                        operator_confirmed=True,
                    )
                )
                snapshot = await service.snapshot()
                robot_statuses = await service.robot_statuses()
                return status, snapshot, robot_statuses, service.events(limit=None)

        status, snapshot, robot_statuses, events = asyncio.run(_run())

        self.assertEqual(status.runtime_mode, RuntimeMode.LIVE)
        self.assertFalse(status.dry_run)
        self.assertTrue(status.live_adapter_ready)
        self.assertEqual(snapshot.runtime.runtime_mode, RuntimeMode.LIVE)
        self.assertFalse(snapshot.runtime.dry_run)
        self.assertTrue(all(robot.mode == RuntimeMode.LIVE for robot in robot_statuses))
        self.assertIn(EventType.RUNTIME_CONFIG_UPDATED, [event.event_type for event in events])

    def test_cyberwave_discovery_reads_local_environment_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OrchestratorService(self.cyberwave_config(tmpdir))
            robots = service.discover_cyberwave_robots()

        go2 = next(robot for robot in robots if robot.robot_id == "go2")
        ugv = next(robot for robot in robots if robot.robot_id == "ugv-beast")
        self.assertEqual(go2.registry_id, "unitree/go2")
        self.assertTrue(go2.has_stream)
        self.assertEqual(go2.browser_url, "http://localhost:8091")
        self.assertIn("move_forward", go2.available_actions)
        self.assertEqual(ugv.registry_id, "waveshare/ugv-beast")

    def test_robot_activation_requires_operator_confirmation(self) -> None:
        async def _run():
            with tempfile.TemporaryDirectory() as tmpdir:
                service = OrchestratorService(self.cyberwave_config(tmpdir))
                with self.assertRaises(PermissionError):
                    await service.activate_robot("go2", RobotActivationRequest())
                return service.events(limit=None)

        events = asyncio.run(_run())

        self.assertNotIn(EventType.ROBOT_ACTIVATION_UPDATED, [event.event_type for event in events])

    def test_virtual_base_movement_updates_pose_without_mqtt(self) -> None:
        async def _run():
            with tempfile.TemporaryDirectory() as tmpdir:
                service = OrchestratorService(self.cyberwave_config(tmpdir))
                fake_mqtt = FakeMqttPublisher()
                service.fleet["go2"].mqtt_publisher = fake_mqtt
                await service.update_runtime(
                    RuntimeConfigRequest(
                        runtime_mode=RuntimeMode.SIMULATION,
                        dry_run=True,
                        operator_confirmed=True,
                    )
                )
                await service.activate_robot(
                    "go2",
                    RobotActivationRequest(operator_confirmed=True),
                )
                result = await service.move_robot_base(
                    "go2",
                    BaseMovementCommand(
                        action=BaseMovementAction.MOVE_FORWARD,
                        movement_target=MovementTarget.VIRTUAL,
                        operator_confirmed=True,
                        distance_m=0.25,
                    ),
                )
                return result, fake_mqtt.messages

        result, messages = asyncio.run(_run())

        self.assertTrue(result.virtual_applied)
        self.assertFalse(result.physical_applied)
        self.assertEqual(messages, [])
        self.assertAlmostEqual(result.pose.x, 0.45)
        self.assertTrue(result.executed_sequence[-1].startswith("virtual_pose:"))

    def test_physical_base_movement_requires_armed_robot(self) -> None:
        async def _run():
            with tempfile.TemporaryDirectory() as tmpdir:
                service = OrchestratorService(self.cyberwave_config(tmpdir))
                await service.update_runtime(
                    RuntimeConfigRequest(
                        runtime_mode=RuntimeMode.LIVE,
                        dry_run=False,
                        operator_confirmed=True,
                    )
                )
                with self.assertRaises(PermissionError):
                    await service.move_robot_base(
                        "go2",
                        BaseMovementCommand(
                            action=BaseMovementAction.MOVE_FORWARD,
                            movement_target=MovementTarget.PHYSICAL,
                            operator_confirmed=True,
                        ),
                    )

        asyncio.run(_run())

    def test_live_non_dry_run_base_movement_publishes_mqtt_sequence(self) -> None:
        async def _run():
            with tempfile.TemporaryDirectory() as tmpdir:
                service = OrchestratorService(self.config(tmpdir))
                fake_mqtt = FakeMqttPublisher()
                service.fleet["go2"].mqtt_publisher = fake_mqtt
                await service.update_runtime(
                    RuntimeConfigRequest(
                        runtime_mode=RuntimeMode.LIVE,
                        dry_run=False,
                        operator_confirmed=True,
                    )
                )
                await service.activate_robot(
                    "go2",
                    RobotActivationRequest(
                        operator_confirmed=True,
                        activation_mode=RobotActivationMode.ARMED,
                        allow_physical=True,
                    ),
                )
                result = await service.move_robot_base(
                    "go2",
                    BaseMovementCommand(
                        action=BaseMovementAction.MOVE_FORWARD,
                        movement_target=MovementTarget.PHYSICAL,
                        operator_confirmed=True,
                        distance_m=0.25,
                    ),
                )
                return result, fake_mqtt.messages

        result, messages = asyncio.run(_run())

        self.assertTrue(result.applied)
        self.assertFalse(result.dry_run)
        self.assertEqual([payload["sequence_step"] for _, payload in messages], [
            "stop_before_motion",
            "move_forward",
            "stop_after_motion",
        ])
        self.assertEqual([payload["action"] for _, payload in messages], [
            "stop",
            "move_forward",
            "stop",
        ])
        self.assertTrue(all(topic == "safeground/robots/go2/commands" for topic, _ in messages))

    def test_cyberwave_replay_dry_run_publishes_recorded_frames_channel(self) -> None:
        calls: list[dict] = []

        def backend_factory():
            return "fake-backend"

        def replay_fn(backend, path, *, channels, speed, loop):
            calls.append(
                {
                    "backend": backend,
                    "path": path,
                    "channels": channels,
                    "speed": speed,
                    "loop": loop,
                }
            )
            return FakeReplayResult()

        with tempfile.TemporaryDirectory() as tmpdir:
            result = replay_cyberwave_recording(
                Path(tmpdir),
                speed=2.0,
                backend_factory=backend_factory,
                replay_fn=replay_fn,
            )

        self.assertTrue(result.dry_run)
        self.assertEqual(result.samples_published, 3)
        self.assertEqual(result.channels, ["frames/default"])
        self.assertEqual(calls[0]["backend"], "fake-backend")
        self.assertEqual(calls[0]["channels"], ["frames/default"])
        self.assertEqual(calls[0]["speed"], 2.0)
        self.assertFalse(calls[0]["loop"])

    def test_camera_object_mark_updates_latest_report(self) -> None:
        async def _run():
            with tempfile.TemporaryDirectory() as tmpdir:
                service = OrchestratorService(self.config(tmpdir))
                await service.start_mission("FIELD")
                report = await service.mark_latest_object(
                    ObjectMarkRequest(
                        label=ClassificationLabel.NOT_MINE,
                        operator_id="operator",
                    ),
                )
                return report, service.events(limit=None)

        report, events = asyncio.run(_run())

        self.assertIsNotNone(report.classification)
        self.assertEqual(report.classification.label, ClassificationLabel.NOT_MINE)
        self.assertTrue(report.safe_to_contact)
        self.assertIsNotNone(report.finding)
        self.assertEqual(report.finding.label, ClassificationLabel.NOT_MINE)
        self.assertIn(EventType.OBJECT_MARKED, [event.event_type for event in events])

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

    def test_object_pickup_workflow_records_manual_so101_template(self) -> None:
        async def _run():
            with tempfile.TemporaryDirectory() as tmpdir:
                service = OrchestratorService(self.config(tmpdir))
                session = await service.start_object_pickup(
                    ObjectPickupStartRequest(
                        operator_confirmed=True,
                        object_label="safe_canister",
                    )
                )
                await service.manual_arm_takeover(
                    "so101",
                    ManualArmCommand(
                        action=ManualArmAction.NUDGE_JOINT,
                        operator_confirmed=True,
                        joint_name="gripper",
                        delta_degrees=1.5,
                    ),
                )
                saved = await service.finish_object_pickup(
                    ObjectPickupFinishRequest(session_id=session.session_id)
                )
                replayed = await service.replay_object_pickup(
                    ObjectPickupReplayRequest(
                        session_id=session.session_id,
                        operator_confirmed=True,
                    )
                )
                snapshot = await service.snapshot()
                return saved, replayed, snapshot, service.events(limit=None)

        saved, replayed, snapshot, events = asyncio.run(_run())

        self.assertEqual(saved.object_label, "safe_canister")
        self.assertEqual(saved.status, "saved")
        self.assertEqual(saved.steps[0].action, "stand_down")
        self.assertEqual(saved.steps[1].action, ManualArmAction.NUDGE_JOINT)
        self.assertEqual(replayed.replay_count, 1)
        self.assertEqual(snapshot.object_pickup_sessions[0].session_id, saved.session_id)
        event_types = [event.event_type for event in events]
        self.assertIn(EventType.OBJECT_PICKUP_SESSION_STARTED, event_types)
        self.assertIn(EventType.OBJECT_PICKUP_STEP_RECORDED, event_types)
        self.assertIn(EventType.OBJECT_PICKUP_SESSION_FINISHED, event_types)
        self.assertIn(EventType.OBJECT_PICKUP_TEMPLATE_REPLAYED, event_types)

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

    def test_go2_scout_route_plan_records_point_map(self) -> None:
        async def _run():
            with tempfile.TemporaryDirectory() as tmpdir:
                service = OrchestratorService(self.config(tmpdir))
                result = await service.plan_scout_route(
                    ScoutRouteCommand(
                        operator_confirmed=True,
                        waypoints=[
                            MapPoint(x=0.1, y=0.8),
                            MapPoint(x=0.4, y=0.5),
                            MapPoint(x=0.8, y=0.2),
                        ],
                    )
                )
                snapshot = await service.snapshot()
                return result, snapshot, service.events(limit=None)

        result, snapshot, events = asyncio.run(_run())

        self.assertTrue(result.accepted)
        self.assertTrue(result.dry_run)
        self.assertEqual(result.robot_id, "go2")
        self.assertEqual(len(result.waypoints), 3)
        self.assertTrue(result.obstacles)
        self.assertEqual(snapshot.scout_route, result)
        event_types = [event.event_type for event in events]
        self.assertIn(EventType.SCOUT_ROUTE_PLANNED, event_types)
        self.assertIn(EventType.POINT_MAP_UPDATED, event_types)

    def test_fastapi_app_imports_with_registered_routes(self) -> None:
        from safeground.api.server import app

        paths = {route.path for route in app.routes}

        self.assertIn("/api/missions/start", paths)
        self.assertIn("/api/runtime", paths)
        self.assertIn("/api/cyberwave/robots", paths)
        self.assertIn("/api/observations/mark", paths)
        self.assertIn("/api/robots", paths)
        self.assertIn("/api/robots/{robot_id}/activate", paths)
        self.assertIn("/api/robots/{robot_id}/manual-arm", paths)
        self.assertIn("/api/robots/{robot_id}/move", paths)
        self.assertIn("/api/robots/go2/route-plan", paths)
        self.assertIn("/api/camera-streams", paths)
        self.assertIn("/api/object-pickup/sessions", paths)
        self.assertIn("/api/object-pickup/start", paths)
        self.assertIn("/api/object-pickup/finish", paths)
        self.assertIn("/api/object-pickup/replay", paths)
        self.assertIn("/ws/events", paths)


if __name__ == "__main__":
    unittest.main()
