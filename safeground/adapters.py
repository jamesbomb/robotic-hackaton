from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from safeground.models import FrameRef, SafeGroundConfig


class MockRobotAdapter:
    def __init__(self, config: SafeGroundConfig) -> None:
        self.id = config.robot_id
        self.role = config.robot_role
        self.sensor_id = config.sensor_id
        self.frame_fixture_dir = config.frame_fixture_dir
        self.output_frame_dir = Path("safeground_runs/frames")

    async def health(self) -> dict:
        return {
            "online": True,
            "mode": "mock",
            "dry_run_safe": True,
            "note": "No hardware commands are sent by the mock adapter.",
        }

    async def capabilities(self) -> dict:
        return {
            "sensors": [self.sensor_id],
            "actions": ["capture_frame", "stop", "hold_position"],
            "unsupported_p0_actions": ["relative_move_short", "rotate_in_place_short"],
        }

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

    async def stop(self) -> None:
        return None
