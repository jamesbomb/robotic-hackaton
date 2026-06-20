from __future__ import annotations

import math
import shutil
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from safeground.mqtt_bridge import MqttPublisher, PahoMqttPublisher
from safeground.models import (
    BaseMovementAction,
    BaseMovementCommand,
    BaseMovementResult,
    FrameRef,
    ManualArmAction,
    ManualArmCommand,
    ManualArmResult,
    MovementTarget,
    RobotPose,
    RobotStatus,
    RuntimeMode,
    SafeGroundConfig,
)


class RobotAdapter(Protocol):
    id: str
    role: str
    sensor_id: str
    pose: RobotPose

    async def health(self) -> dict: ...

    async def capabilities(self) -> dict: ...

    async def status(self) -> RobotStatus: ...

    async def capture_frame(self, sensor_id: str | None = None) -> FrameRef: ...

    async def hold_position(self) -> None: ...

    async def stop(self) -> None: ...

    async def execute_base_movement(self, command: BaseMovementCommand) -> BaseMovementResult: ...

    async def execute_manual_arm_command(self, command: ManualArmCommand) -> ManualArmResult: ...


class MockRobotAdapter:
    def __init__(
        self,
        config: SafeGroundConfig,
        *,
        robot_id: str | None = None,
        role: str | None = None,
        sensor_id: str | None = None,
        sensors: list[str] | None = None,
        actions: list[str] | None = None,
        pose: RobotPose | None = None,
        battery_percent: int | None = 100,
        task: str = "idle",
        note: str | None = None,
        mqtt_publisher: MqttPublisher | None = None,
    ) -> None:
        self.id = robot_id or config.robot_id
        self.role = role or config.robot_role
        self.sensor_id = sensor_id or config.sensor_id
        self.sensors = sensors or [self.sensor_id]
        self.actions = actions or [
            "capture_frame",
            "stop",
            "hold_position",
            "move_forward",
            "move_backward",
            "strafe_left",
            "strafe_right",
            "rotate_left",
            "rotate_right",
        ]
        self.pose = pose or RobotPose()
        self.battery_percent = battery_percent
        self.task = task
        self.note = note or "No hardware commands are sent by the mock adapter."
        self.runtime_mode = config.runtime_mode
        self.dry_run = config.dry_run
        self.mqtt_topic_prefix = config.mqtt_topic_prefix
        self.mqtt_publisher = mqtt_publisher or PahoMqttPublisher(
            host=config.mqtt_host,
            port=config.mqtt_port,
            qos=config.mqtt_qos,
            timeout_s=config.mqtt_timeout_s,
            client_id=f"safeground-{self.id}",
        )
        self.frame_fixture_dir = config.frame_fixture_dir
        self.output_frame_dir = Path("safeground_runs/frames")

    async def health(self) -> dict:
        return {
            "online": True,
            "mode": self.runtime_mode,
            "adapter": "mock",
            "dry_run_safe": self.dry_run,
            "note": self.note,
        }

    async def capabilities(self) -> dict:
        return {
            "sensors": self.sensors,
            "actions": self.actions,
            "unsupported_p0_actions": ["waypoint_navigation", "continuous_velocity"],
        }

    async def status(self) -> RobotStatus:
        return RobotStatus(
            robot_id=self.id,
            role=self.role,
            online=True,
            mode=self.runtime_mode,
            task=self.task,
            battery_percent=self.battery_percent,
            sensors=self.sensors,
            actions=self.actions,
            pose=self.pose,
            note=self.note,
        )

    async def capture_frame(self, sensor_id: str | None = None) -> FrameRef:
        selected_sensor = sensor_id or self.sensor_id
        fixture = self.frame_fixture_dir / "mock-target.txt"
        frame_id = f"{selected_sensor}-{uuid4().hex[:8]}"
        self.output_frame_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.output_frame_dir / f"{frame_id}.txt"
        shutil.copyfile(fixture, output_path)
        return FrameRef(
            frame_id=frame_id,
            sensor_id=selected_sensor,
            source="fixture",
            path=output_path,
            width=640,
            height=480,
            metadata={"fixture": str(fixture), "adapter": self.id},
        )

    async def hold_position(self) -> None:
        self.task = "holding"
        return None

    async def stop(self) -> None:
        self.task = "stopped"
        return None

    async def execute_base_movement(self, command: BaseMovementCommand) -> BaseMovementResult:
        if command.action.value not in self.actions:
            return BaseMovementResult(
                robot_id=self.id,
                action=command.action,
                applied=False,
                dry_run=True,
                pose=self.pose,
                movement_target=command.movement_target,
                reason=f"{self.id} does not expose base movement.",
            )

        self.task = "manual_base_movement"
        sequence = ["stop_before_motion", command.action.value, "stop_after_motion"]
        wants_physical = command.movement_target in {MovementTarget.PHYSICAL, MovementTarget.BOTH}
        wants_virtual = command.movement_target in {MovementTarget.VIRTUAL, MovementTarget.BOTH}
        if command.movement_target == MovementTarget.AUTO:
            wants_physical = self.runtime_mode == RuntimeMode.LIVE and not self.dry_run
            wants_virtual = not wants_physical

        if wants_virtual:
            self._apply_virtual_pose(command)

        if wants_physical:
            self._publish_live_base_sequence(command, sequence)
            return BaseMovementResult(
                robot_id=self.id,
                action=command.action,
                applied=True,
                dry_run=False,
                pose=self.pose,
                movement_target=command.movement_target,
                virtual_applied=wants_virtual,
                physical_applied=True,
                executed_sequence=[
                    f"mqtt_publish:{step}" for step in sequence
                ] + (sequence if wants_virtual else []),
                reason=f"{command.reason} Published to MQTT controller policy topic.",
            )

        return BaseMovementResult(
            robot_id=self.id,
            action=command.action,
            applied=True,
            dry_run=True,
            pose=self.pose,
            movement_target=command.movement_target,
            virtual_applied=True,
            physical_applied=False,
            executed_sequence=sequence,
            reason=command.reason,
        )

    def _apply_virtual_pose(self, command: BaseMovementCommand) -> None:
        if command.action == BaseMovementAction.MOVE_FORWARD:
            self.pose.x += command.distance_m * math.cos(self.pose.yaw)
            self.pose.y += command.distance_m * math.sin(self.pose.yaw)
        elif command.action == BaseMovementAction.MOVE_BACKWARD:
            self.pose.x -= command.distance_m * math.cos(self.pose.yaw)
            self.pose.y -= command.distance_m * math.sin(self.pose.yaw)
        elif command.action == BaseMovementAction.STRAFE_LEFT:
            self.pose.x += command.distance_m * math.cos(self.pose.yaw + math.pi / 2)
            self.pose.y += command.distance_m * math.sin(self.pose.yaw + math.pi / 2)
        elif command.action == BaseMovementAction.STRAFE_RIGHT:
            self.pose.x += command.distance_m * math.cos(self.pose.yaw - math.pi / 2)
            self.pose.y += command.distance_m * math.sin(self.pose.yaw - math.pi / 2)
        elif command.action == BaseMovementAction.ROTATE_LEFT:
            self.pose.yaw += math.radians(command.angle_degrees)
        elif command.action == BaseMovementAction.ROTATE_RIGHT:
            self.pose.yaw -= math.radians(command.angle_degrees)

    def _publish_live_base_sequence(
        self,
        command: BaseMovementCommand,
        sequence: list[str],
    ) -> None:
        topic = f"{self.mqtt_topic_prefix}/{self.id}/commands"
        for step in sequence:
            action = "stop" if step in {"stop_before_motion", "stop_after_motion"} else command.action.value
            self.mqtt_publisher.publish(
                topic,
                {
                    "source": "safeground",
                    "robot_id": self.id,
                    "runtime_mode": self.runtime_mode,
                    "dry_run": False,
                    "sequence_step": step,
                    "action": action,
                    "distance_m": command.distance_m,
                    "angle_degrees": command.angle_degrees,
                    "operator_id": command.operator_id,
                    "reason": command.reason,
                },
            )

    async def execute_manual_arm_command(self, command: ManualArmCommand) -> ManualArmResult:
        return ManualArmResult(
            robot_id=self.id,
            action=command.action,
            applied=False,
            dry_run=True,
            reason=f"{self.id} does not expose SO-101 manual arm control.",
        )


class MockSO101ArmAdapter(MockRobotAdapter):
    def __init__(self, config: SafeGroundConfig) -> None:
        super().__init__(
            config,
            robot_id="so101",
            role="Marker Agent",
            sensor_id="so101-wrist-camera",
            sensors=["joint_states", "so101-wrist-camera"],
            actions=[
                "stop",
                "hold_position",
                "manual_arm_home",
                "manual_arm_hold_position",
                "manual_arm_nudge_joint",
                "manual_arm_place_safe_marker",
            ],
            pose=RobotPose(x=0.0, y=1.2, yaw=0.0),
            battery_percent=None,
            note="Mock SO-101 marker agent; human takeover uses bounded dry-run commands.",
        )
        self.joint_positions_degrees = {joint: 0.0 for joint in config.so101_allowed_joints}

    async def execute_base_movement(self, command: BaseMovementCommand) -> BaseMovementResult:
        return BaseMovementResult(
            robot_id=self.id,
            action=command.action,
            applied=False,
            dry_run=True,
            pose=self.pose,
            movement_target=command.movement_target,
            reason="SO-101 is a fixed arm and cannot execute base movement.",
        )

    async def capabilities(self) -> dict:
        capabilities = await super().capabilities()
        capabilities["manual_arm"] = {
            "joints": sorted(self.joint_positions_degrees),
            "max_step_degrees": 5.0,
            "requires_operator_confirmation": True,
            "safe_marker_only": True,
        }
        capabilities["unsupported_p0_actions"] = []
        return capabilities

    async def execute_manual_arm_command(self, command: ManualArmCommand) -> ManualArmResult:
        self.task = "human_takeover"
        sequence: list[str]

        if command.action == ManualArmAction.HOME:
            self.joint_positions_degrees = {
                joint: 0.0 for joint in self.joint_positions_degrees
            }
            sequence = ["stop", "home"]
        elif command.action == ManualArmAction.HOLD_POSITION:
            sequence = ["hold_position"]
        elif command.action == ManualArmAction.NUDGE_JOINT and command.joint_name is not None:
            self.joint_positions_degrees[command.joint_name] += command.delta_degrees
            sequence = [f"nudge:{command.joint_name}:{command.delta_degrees:+.1f}deg"]
        elif command.action == ManualArmAction.PLACE_SAFE_MARKER:
            sequence = [
                "stop",
                "move_to_prevalidated_safe_marker_pose",
                "release_marker",
                "home",
            ]
        else:
            sequence = ["rejected_by_adapter"]

        return ManualArmResult(
            robot_id=self.id,
            action=command.action,
            applied=sequence != ["rejected_by_adapter"],
            dry_run=True,
            joint_name=command.joint_name,
            joint_positions_degrees=dict(sorted(self.joint_positions_degrees.items())),
            executed_sequence=sequence,
            reason=command.reason,
        )


def build_mock_fleet(config: SafeGroundConfig) -> dict[str, RobotAdapter]:
    return {
        "go2": MockRobotAdapter(
            config,
            robot_id="go2",
            role="Primary Scout",
            sensor_id="go2-front-camera",
            sensors=["go2-front-camera", "lidar", "pose"],
            pose=RobotPose(x=0.2, y=0.3, yaw=0.0),
            battery_percent=87,
            note="Mock Unitree Go2 scout; dry-run only.",
        ),
        "ugv-beast": MockRobotAdapter(
            config,
            robot_id="ugv-beast",
            role="Verification Scout",
            sensor_id="ugv-pan-tilt-camera",
            sensors=["ugv-pan-tilt-camera", "imu", "battery"],
            pose=RobotPose(x=1.1, y=0.2, yaw=0.4),
            battery_percent=92,
            note="Mock UGV Beast verifier; dry-run only.",
        ),
        "so101": MockSO101ArmAdapter(config),
        "fixed-camera": MockRobotAdapter(
            config,
            robot_id="fixed-camera",
            role="Overview Sensor",
            sensor_id="overview-camera",
            sensors=["overview-camera"],
            actions=["capture_frame", "stop", "hold_position"],
            pose=RobotPose(x=0.0, y=0.0, yaw=0.0),
            battery_percent=None,
            note="Mock fixed overview camera fallback.",
        ),
    }
