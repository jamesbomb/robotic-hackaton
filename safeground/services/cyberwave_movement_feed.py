from __future__ import annotations

import json
import math
import os
import threading
import time
from collections.abc import Callable
from typing import Any

from safeground.models import CyberwaveRobot, EventType, RuntimeMode, SafeGroundConfig

EmitEvent = Callable[..., None]
DiscoverRobots = Callable[[], list[CyberwaveRobot]]
ResolveEnvironmentId = Callable[[], str | None]
OpenTwin = Callable[[Any, str, dict[str, str | None], str | None], Any]
ResolveAffectMode = Callable[[], str]

MOBILE_ROBOT_IDS = frozenset({"go2", "ugv-beast", "so101", "so101-ugv"})
DEFAULT_MIN_INTERVAL_S = 2.0
DEFAULT_MIN_POSITION_DELTA_M = 0.03
DEFAULT_MIN_YAW_DELTA_DEG = 3.0


def _parse_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, (bytes, bytearray)):
        try:
            parsed = json.loads(payload.decode("utf-8"))
            return parsed if isinstance(parsed, dict) else {"value": parsed}
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {"raw": payload.decode("utf-8", errors="replace")}
    if isinstance(payload, str):
        try:
            parsed = json.loads(payload)
            return parsed if isinstance(parsed, dict) else {"value": parsed}
        except json.JSONDecodeError:
            return {"raw": payload}
    return {"value": payload}


def _extract_position(payload: dict[str, Any]) -> dict[str, float] | None:
    for key in ("position", "pos"):
        candidate = payload.get(key)
        if isinstance(candidate, dict) and any(axis in candidate for axis in ("x", "y", "z")):
            return {
                axis: float(candidate[axis])
                for axis in ("x", "y", "z")
                if axis in candidate and candidate[axis] is not None
            }
    if any(axis in payload for axis in ("x", "y", "z")):
        return {
            axis: float(payload[axis])
            for axis in ("x", "y", "z")
            if axis in payload and payload[axis] is not None
        }
    return None


def _extract_rotation(payload: dict[str, Any]) -> dict[str, float] | None:
    for key in ("rotation", "rot", "orientation"):
        candidate = payload.get(key)
        if isinstance(candidate, dict):
            if "yaw" in candidate:
                return {"yaw": float(candidate["yaw"])}
            if all(axis in candidate for axis in ("x", "y", "z", "w")):
                return {
                    axis: float(candidate[axis])
                    for axis in ("x", "y", "z", "w")
                    if candidate[axis] is not None
                }
    if "yaw" in payload:
        return {"yaw": float(payload["yaw"])}
    return None


def _position_delta(left: dict[str, float] | None, right: dict[str, float] | None) -> float:
    if not left or not right:
        return float("inf")
    total = 0.0
    for axis in ("x", "y", "z"):
        if axis in left and axis in right:
            total += (left[axis] - right[axis]) ** 2
    return math.sqrt(total)


def _yaw_delta(left: dict[str, float] | None, right: dict[str, float] | None) -> float:
    if not left or not right or "yaw" not in left or "yaw" not in right:
        return float("inf")
    delta = abs(left["yaw"] - right["yaw"]) % 360.0
    return min(delta, 360.0 - delta)


def should_emit_movement_update(
    *,
    now: float,
    last_emit_at: float | None,
    last_position: dict[str, float] | None,
    last_rotation: dict[str, float] | None,
    position: dict[str, float] | None,
    rotation: dict[str, float] | None,
    min_interval_s: float = DEFAULT_MIN_INTERVAL_S,
    min_position_delta_m: float = DEFAULT_MIN_POSITION_DELTA_M,
    min_yaw_delta_deg: float = DEFAULT_MIN_YAW_DELTA_DEG,
) -> bool:
    if last_emit_at is None:
        return True
    if now - last_emit_at < min_interval_s:
        return False
    if _position_delta(last_position, position) >= min_position_delta_m:
        return True
    if _yaw_delta(last_rotation, rotation) >= min_yaw_delta_deg:
        return True
    return False


class CyberwaveMovementFeedMonitor:
    """Subscribe to Cyberwave MQTT movement topics and emit audit events."""

    def __init__(
        self,
        *,
        config: SafeGroundConfig,
        emit_event: EmitEvent,
        discover_robots: DiscoverRobots,
        resolve_environment_id: ResolveEnvironmentId,
        open_twin: OpenTwin,
        resolve_affect_mode: ResolveAffectMode,
        mission_id: Callable[[], str],
    ) -> None:
        self._config = config
        self._emit_event = emit_event
        self._discover_robots = discover_robots
        self._resolve_environment_id = resolve_environment_id
        self._open_twin = open_twin
        self._resolve_affect_mode = resolve_affect_mode
        self._mission_id = mission_id
        self._lock = threading.Lock()
        self._client: Any | None = None
        self._subscribed_robots: list[str] = []
        self._last_emit_at: dict[str, float] = {}
        self._last_position: dict[str, dict[str, float]] = {}
        self._last_rotation: dict[str, dict[str, float]] = {}
        self._affect_mode = "simulation"

    @property
    def active(self) -> bool:
        return self._client is not None

    @property
    def subscribed_robots(self) -> list[str]:
        return list(self._subscribed_robots)

    @property
    def affect_mode(self) -> str:
        return self._affect_mode

    def restart(self) -> None:
        self.stop()
        self.start()

    def start(self) -> None:
        api_key = os.environ.get("CYBERWAVE_API_KEY")
        if not api_key:
            return

        try:
            from cyberwave import Cyberwave
        except ImportError:
            return

        environment_id = self._resolve_environment_id()
        kwargs: dict[str, Any] = {"api_key": api_key}
        if environment_id:
            kwargs["environment_id"] = environment_id

        try:
            client = Cyberwave(**kwargs)
            self._affect_mode = self._resolve_affect_mode()
            client.affect(self._affect_mode)
        except Exception as exc:
            self._emit_event(
                self._mission_id(),
                EventType.ERROR,
                robot_id="cyberwave",
                data={
                    "source": "movement_feed",
                    "reason": "failed_to_start_cyberwave_movement_feed",
                    "error": str(exc),
                },
            )
            return

        subscribed: list[str] = []
        for robot in self._discover_robots():
            if robot.robot_id not in MOBILE_ROBOT_IDS:
                continue
            if robot.twin_uuid.startswith("mock-"):
                continue
            twin_ref = {"twin_uuid": robot.twin_uuid, "slug": robot.slug or robot.registry_id}
            try:
                twin = self._open_twin(client, robot.robot_id, twin_ref, environment_id)
                twin.subscribe_position(
                    lambda payload, robot_id=robot.robot_id, twin_uuid=robot.twin_uuid: self._on_position(
                        robot_id,
                        twin_uuid,
                        payload,
                    )
                )
                twin.subscribe_rotation(
                    lambda payload, robot_id=robot.robot_id, twin_uuid=robot.twin_uuid: self._on_rotation(
                        robot_id,
                        twin_uuid,
                        payload,
                    )
                )
                subscribed.append(robot.robot_id)
            except Exception as exc:
                self._emit_event(
                    self._mission_id(),
                    EventType.ERROR,
                    robot_id=robot.robot_id,
                    data={
                        "source": "movement_feed",
                        "reason": "movement_subscription_failed",
                        "twin_uuid": robot.twin_uuid,
                        "error": str(exc),
                    },
                )

        if not subscribed:
            try:
                if getattr(client, "mqtt", None) and client.mqtt.connected:
                    client.mqtt.disconnect()
            except Exception:
                pass
            return

        self._client = client
        self._subscribed_robots = subscribed
        self._emit_event(
            self._mission_id(),
            EventType.CYBERWAVE_MOVEMENT_FEED_STARTED,
            robot_id="cyberwave",
            data={
                "affect_mode": self._affect_mode,
                "runtime_mode": self._config.runtime_mode,
                "dry_run": self._config.dry_run,
                "robots": subscribed,
            },
        )

    def stop(self) -> None:
        subscribed = list(self._subscribed_robots)
        client = self._client
        self._client = None
        self._subscribed_robots = []
        if client is None:
            return

        try:
            if getattr(client, "mqtt", None) and client.mqtt.connected:
                client.mqtt.disconnect()
        except Exception:
            pass

        if subscribed:
            self._emit_event(
                self._mission_id(),
                EventType.CYBERWAVE_MOVEMENT_FEED_STOPPED,
                robot_id="cyberwave",
                data={"robots": subscribed},
            )

    def _on_position(self, robot_id: str, twin_uuid: str, payload: Any) -> None:
        parsed = _parse_payload(payload)
        position = _extract_position(parsed)
        self._maybe_emit(robot_id, twin_uuid, feed="position", position=position, rotation=None, raw=parsed)

    def _on_rotation(self, robot_id: str, twin_uuid: str, payload: Any) -> None:
        parsed = _parse_payload(payload)
        rotation = _extract_rotation(parsed)
        self._maybe_emit(robot_id, twin_uuid, feed="rotation", position=None, rotation=rotation, raw=parsed)

    def _maybe_emit(
        self,
        robot_id: str,
        twin_uuid: str,
        *,
        feed: str,
        position: dict[str, float] | None,
        rotation: dict[str, float] | None,
        raw: dict[str, Any],
    ) -> None:
        now = time.time()
        with self._lock:
            if not should_emit_movement_update(
                now=now,
                last_emit_at=self._last_emit_at.get(robot_id),
                last_position=self._last_position.get(robot_id),
                last_rotation=self._last_rotation.get(robot_id),
                position=position,
                rotation=rotation,
            ):
                return
            self._last_emit_at[robot_id] = now
            if position is not None:
                self._last_position[robot_id] = position
            if rotation is not None:
                self._last_rotation[robot_id] = rotation

        self._emit_event(
            self._mission_id(),
            EventType.CYBERWAVE_MOVEMENT_FEED,
            robot_id=robot_id,
            data={
                "source": "cyberwave_mqtt",
                "feed": feed,
                "twin_uuid": twin_uuid,
                "affect_mode": self._affect_mode,
                "runtime_mode": self._config.runtime_mode,
                "dry_run": self._config.dry_run,
                "position": position,
                "rotation": rotation,
                "payload": raw,
            },
        )
