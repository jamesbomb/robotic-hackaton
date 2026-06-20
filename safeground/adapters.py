from __future__ import annotations

import shutil
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from safeground.models import FrameRef, RobotPose, RobotStatus, RuntimeMode, SafeGroundConfig


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
    ) -> None:
        self.id = robot_id or config.robot_id
        self.role = role or config.robot_role
        self.sensor_id = sensor_id or config.sensor_id
        self.sensors = sensors or [self.sensor_id]
        self.actions = actions or ["capture_frame", "stop", "hold_position"]
        self.pose = pose or RobotPose()
        self.battery_percent = battery_percent
        self.task = task
        self.note = note or "No hardware commands are sent by the mock adapter."
        self.frame_fixture_dir = config.frame_fixture_dir
        self.output_frame_dir = Path("safeground_runs/frames")

    async def health(self) -> dict:
        return {
            "online": True,
            "mode": "mock",
            "dry_run_safe": True,
            "note": self.note,
        }

    async def capabilities(self) -> dict:
        return {
            "sensors": self.sensors,
            "actions": self.actions,
            "unsupported_p0_actions": ["relative_move_short", "rotate_in_place_short"],
        }

    async def status(self) -> RobotStatus:
        return RobotStatus(
            robot_id=self.id,
            role=self.role,
            online=True,
            mode=RuntimeMode.MOCK,
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
        "so101": MockRobotAdapter(
            config,
            robot_id="so101",
            role="Marker Agent",
            sensor_id="so101-wrist-camera",
            sensors=["joint_states", "so101-wrist-camera"],
            actions=["stop", "hold_position"],
            pose=RobotPose(x=0.0, y=1.2, yaw=0.0),
            battery_percent=None,
            note="Mock SO-101 marker agent; marker motion disabled in P0.",
        ),
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
