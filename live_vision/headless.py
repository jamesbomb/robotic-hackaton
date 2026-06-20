"""Headless live_vision loop (same SENSE as vision.py, no OpenCV window)."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import cv2
import numpy as np

VLM_PERIOD_S = 5.0
FRAME_SIZE = (960, 540)


@dataclass
class VisionLoopStatus:
    running: bool = False
    source: str = "camera"
    camera_index: int = 0
    robot_id: str = "go2"
    vlm_state: str = "idle"
    last_error: str | None = None
    last_detection_count: int = 0
    last_model_id: str | None = None
    last_frame_id: str | None = None
    fps: float = 0.0


FetchRobotFrame = Callable[[str], bytes | None]
OnClassified = Callable[[dict[str, Any]], None]


class HeadlessVisionLoop:
    """Background capture + VLM classify loop (VLM always on, like vision.py with V pressed)."""

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._latest_jpeg: bytes | None = None
        self._status = VisionLoopStatus()
        self._source = "camera"
        self._camera_index = 0
        self._robot_id = "go2"
        self._fetch_robot_frame: FetchRobotFrame | None = None
        self._on_classified: OnClassified | None = None

    def configure(
        self,
        *,
        source: str,
        camera_index: int = 0,
        robot_id: str = "go2",
        fetch_robot_frame: FetchRobotFrame | None = None,
        on_classified: OnClassified | None = None,
    ) -> None:
        self._source = source
        self._camera_index = camera_index
        self._robot_id = robot_id
        self._fetch_robot_frame = fetch_robot_frame
        self._on_classified = on_classified
        with self._lock:
            self._status.source = source
            self._status.camera_index = camera_index
            self._status.robot_id = robot_id

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="live-vision", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._thread = None
        with self._lock:
            self._status.running = False

    def restart(self) -> None:
        self.stop()
        self.start()

    def latest_frame_jpeg(self) -> bytes | None:
        with self._lock:
            return self._latest_jpeg

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "running": self._status.running,
                "source": self._status.source,
                "camera_index": self._status.camera_index,
                "robot_id": self._status.robot_id,
                "vlm_state": self._status.vlm_state,
                "last_error": self._status.last_error,
                "last_detection_count": self._status.last_detection_count,
                "last_model_id": self._status.last_model_id,
                "last_frame_id": self._status.last_frame_id,
                "fps": round(self._status.fps, 1),
            }

    def _set_status(self, **kwargs: Any) -> None:
        with self._lock:
            for key, value in kwargs.items():
                setattr(self._status, key, value)

    def _store_jpeg(self, frame_bgr: np.ndarray) -> None:
        ok, buf = cv2.imencode(".jpg", frame_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
        if not ok:
            return
        with self._lock:
            self._latest_jpeg = buf.tobytes()

    def _open_camera(self, index: int):
        cap = cv2.VideoCapture(index)
        return cap if cap.isOpened() else None

    def _read_robot_frame(self) -> np.ndarray | None:
        if self._fetch_robot_frame is None:
            return None
        try:
            frame_bytes = self._fetch_robot_frame(self._robot_id)
        except Exception as exc:
            self._set_status(last_error=str(exc))
            return None
        if not frame_bytes:
            return None
        frame = cv2.imdecode(np.frombuffer(frame_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        return frame

    def _run(self) -> None:
        import cw_vision

        self._set_status(running=True, last_error=None, vlm_state="starting")
        cap = None
        last_vlm = 0.0
        t0 = time.time()
        fps = 0.0

        try:
            if self._source == "robot":
                if self._fetch_robot_frame is None:
                    self._set_status(running=False, vlm_state="error", last_error="Robot frame fetcher missing.")
                    return
            else:
                cap = self._open_camera(self._camera_index)
                if cap is None:
                    self._set_status(
                        running=False,
                        vlm_state="error",
                        last_error=f"Camera index {self._camera_index} not available.",
                    )
                    return

            self._set_status(vlm_state="idle")

            while not self._stop.is_set():
                if self._source == "robot":
                    frame = self._read_robot_frame()
                    if frame is None:
                        time.sleep(0.2)
                        continue
                else:
                    ok, frame = cap.read()
                    if not ok or frame is None:
                        time.sleep(0.05)
                        continue

                frame = cv2.resize(frame, FRAME_SIZE)
                self._store_jpeg(frame)

                now = time.time()
                dt = now - t0
                t0 = now
                if dt > 0:
                    fps = 0.9 * fps + 0.1 * (1.0 / dt)
                self._set_status(fps=fps)

                if now - last_vlm < VLM_PERIOD_S:
                    time.sleep(0.02)
                    continue

                last_vlm = now
                self._set_status(vlm_state="analyzing")
                try:
                    detections = cw_vision.classify(frame)
                    model_id = "google/models/gemini-robotics-er-16"
                    frame_id = f"vision-{int(now * 1000)}"
                    robot_id = self._robot_id if self._source == "robot" else "pc-camera"
                    payload = {
                        "frame_id": frame_id,
                        "robot_id": robot_id,
                        "source": self._source,
                        "model_id": model_id,
                        "detections": [{k: v for k, v in d.items() if not str(k).startswith("_")} for d in detections],
                        "detection_count": len(detections),
                        "frame_width": frame.shape[1],
                        "frame_height": frame.shape[0],
                        "valid": bool(detections),
                        "validation_errors": [] if detections else ["No detections from VLM."],
                    }
                    callback = self._on_classified
                    if callback is not None:
                        callback(payload, frame)
                    self._set_status(
                        vlm_state="done",
                        last_error=None,
                        last_detection_count=len(detections),
                        last_model_id=model_id,
                        last_frame_id=frame_id,
                    )
                except Exception as exc:
                    self._set_status(vlm_state="error", last_error=str(exc)[:240])
                time.sleep(0.02)
        finally:
            if cap is not None:
                cap.release()
            self._set_status(running=False, vlm_state="stopped")
