from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from typing import Any

from safeground.env import env_bool
from safeground.models import CameraSource, EventType


class LiveVisionWorker:
    """Starts live_vision/headless.py automatically with the SafeGround backend."""

    def __init__(self, orchestrator: Any) -> None:
        self._orchestrator = orchestrator
        self._loop = None
        self._started = False
        self._lock = threading.Lock()
        self._latest_result: dict[str, Any] | None = None

    def start(self) -> None:
        if not env_bool("SAFEGROUND_LIVE_VISION", True):
            return
        live_vision_dir = Path(__file__).resolve().parents[2] / "live_vision"
        if live_vision_dir.exists() and str(live_vision_dir) not in sys.path:
            sys.path.insert(0, str(live_vision_dir))
        try:
            from headless import HeadlessVisionLoop
        except ImportError:
            return

        camera_index = int(os.environ.get("SAFEGROUND_VISION_CAMERA_INDEX", "0"))
        if self._loop is None:
            self._loop = HeadlessVisionLoop()
        self._apply_config()
        self._loop.configure(
            source=self._current_source(),
            camera_index=camera_index,
            robot_id=self._orchestrator.config.robot_id,
            fetch_robot_frame=self._fetch_robot_frame,
            on_classified=self._on_classified,
        )
        self._loop.start()
        self._started = True
        self._orchestrator.event_store.emit(
            self._orchestrator._movement_feed_mission_id(),
            EventType.VISION_LOOP_STARTED,
            robot_id=self._orchestrator.config.robot_id,
            data=self.status(),
        )

    def stop(self) -> None:
        self._started = False
        if self._loop is not None:
            self._loop.stop()
            self._orchestrator.event_store.emit(
                self._orchestrator._movement_feed_mission_id(),
                EventType.VISION_LOOP_STOPPED,
                robot_id=self._orchestrator.config.robot_id,
                data=self.status(),
            )

    def restart(self) -> None:
        if not self._started and not env_bool("SAFEGROUND_LIVE_VISION", True):
            return
        if self._loop is None:
            self.start()
            return
        self._apply_config()
        camera_index = int(os.environ.get("SAFEGROUND_VISION_CAMERA_INDEX", "0"))
        self._loop.configure(
            source=self._current_source(),
            camera_index=camera_index,
            robot_id=self._orchestrator.config.robot_id,
            fetch_robot_frame=self._fetch_robot_frame,
            on_classified=self._on_classified,
        )
        self._loop.restart()
        self._started = True

    def status(self) -> dict[str, Any]:
        if self._loop is None:
            return {"running": False, "enabled": env_bool("SAFEGROUND_LIVE_VISION", True)}
        status = self._loop.status()
        status["enabled"] = env_bool("SAFEGROUND_LIVE_VISION", True)
        return status

    def latest_frame_jpeg(self) -> bytes | None:
        if self._loop is None:
            return None
        return self._loop.latest_frame_jpeg()

    def latest_result(self) -> dict[str, Any] | None:
        with self._lock:
            return self._latest_result

    def _current_source(self) -> str:
        if self._orchestrator.config.camera_source == CameraSource.ROBOT:
            return "robot"
        return "camera"

    def _apply_config(self) -> None:
        if self._loop is None:
            return
        self._loop.configure(
            source=self._current_source(),
            camera_index=int(os.environ.get("SAFEGROUND_VISION_CAMERA_INDEX", "0")),
            robot_id=self._orchestrator.config.robot_id,
            fetch_robot_frame=self._fetch_robot_frame,
            on_classified=self._on_classified,
        )

    def _fetch_robot_frame(self, robot_id: str) -> bytes | None:
        try:
            return self._orchestrator._fetch_latest_robot_frame_sync(robot_id)
        except Exception:
            return None

    def _on_classified(self, payload: dict[str, Any], frame_bgr) -> None:
        import cv2

        ok, buf = cv2.imencode(".jpg", frame_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
        frame_bytes = buf.tobytes() if ok else b""
        robot_id = str(payload.get("robot_id") or "pc-camera")
        frame_id = str(payload.get("frame_id") or f"vision-{robot_id}")
        result = self._orchestrator.ingest_live_vision_result(
            payload,
            frame_bytes=frame_bytes,
            robot_id=robot_id,
            frame_id=frame_id,
        )
        with self._lock:
            self._latest_result = result
