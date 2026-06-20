from __future__ import annotations

import asyncio
import base64
import binascii
import json
import math
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from safeground.adapters import RobotAdapter, build_mock_fleet
from safeground.agents import MovementCommandAgent, OperatorCommandAgent, OrchestratorAgent
from safeground.cv import MockCVClient
from safeground.env import env_bool, load_local_env
from safeground.event_store import Event, JsonlEventStore
from safeground.mission import MissionRunner
from safeground.models import (
    AgentDecisionType,
    BaseMovementCommand,
    BaseMovementResult,
    CameraStream,
    CameraSource,
    ClassificationLabel,
    ClassificationResult,
    CommandRequest,
    EventType,
    Finding,
    FrameRef,
    ImageClassifyRequest,
    ManualArmCommand,
    ManualArmResult,
    MapObstacle,
    MapPoint,
    MovementAgentPlan,
    MovementCommandRequest,
    MovementCommandResult,
    MovementControllerState,
    MovementFSMState,
    MissionReport,
    MissionSnapshot,
    MissionState,
    MovementTarget,
    ObjectMarkRequest,
    ObjectPickupFinishRequest,
    ObjectPickupReplayRequest,
    ObjectPickupSession,
    ObjectPickupStartRequest,
    ObjectPickupStep,
    RecommendedAction,
    RobotActivationMode,
    RobotActivationRequest,
    RobotActivationState,
    RobotStatus,
    RuntimeConfigRequest,
    RuntimeMode,
    RuntimeStatus,
    SafeGroundConfig,
    ScoutRouteCommand,
    ScoutRouteResult,
    CyberwaveRobot,
    RiskMapState,
)
from safeground.safety import SafetyGovernor
from safeground.services.cyberwave_movement_feed import CyberwaveMovementFeedMonitor
from safeground.services.live_vision_worker import LiveVisionWorker


class OrchestratorService:
    def __init__(self, config: SafeGroundConfig | None = None) -> None:
        load_local_env()
        runtime_mode = RuntimeMode(os.environ.get("SAFEGROUND_RUNTIME_MODE", RuntimeMode.MOCK.value))
        self.config = config or SafeGroundConfig(
            runtime_mode=runtime_mode,
            dry_run=env_bool("SAFEGROUND_DRY_RUN", True),
        )
        self.event_store = JsonlEventStore(self.config.event_log_path)
        self.fleet = build_mock_fleet(self.config)
        self.latest_report: MissionReport | None = None
        self.latest_scout_route: ScoutRouteResult | None = None
        self.object_pickup_sessions: list[ObjectPickupSession] = []
        self.active_object_pickup_session: ObjectPickupSession | None = None
        self.robot_activations: dict[str, RobotActivationState] = {
            robot_id: RobotActivationState(robot_id=robot_id)
            for robot_id in self.fleet
        }
        self.movement_controller = MovementControllerState()
        self.active_runner: MissionRunner | None = None
        self._movement_feed_monitor = CyberwaveMovementFeedMonitor(
            config=self.config,
            emit_event=self.event_store.emit,
            discover_robots=lambda: self.discover_cyberwave_robots(emit_event=False),
            resolve_environment_id=self._resolve_cyberwave_environment_id,
            open_twin=self._open_cyberwave_twin,
            resolve_affect_mode=self._resolve_cyberwave_movement_affect_mode,
            mission_id=self._movement_feed_mission_id,
        )
        self._movement_feed_started = False
        self.risk_map_grid = self._build_risk_map_grid()
        self._live_vision_worker = LiveVisionWorker(self)
        self._latest_vision_result: dict | None = None
        self._sync_adapter_runtime()
        self._load_object_pickup_sessions()

    async def robot_statuses(self) -> list[RobotStatus]:
        return [await robot.status() for robot in self.fleet.values()]

    def runtime_status(self) -> RuntimeStatus:
        return RuntimeStatus(
            runtime_mode=self.config.runtime_mode,
            dry_run=self.config.dry_run,
            robot_movement_target=self.config.robot_movement_target,
            camera_source=self.config.camera_source,
            live_adapter_ready=self.config.runtime_mode == RuntimeMode.LIVE and not self.config.dry_run,
            note=(
                "Physical robot target and onboard robot cameras selected; arm each robot before moving hardware."
                if self.config.runtime_mode == RuntimeMode.LIVE and not self.config.dry_run
                else "Simulation-safe mode selected; robot commands stay virtual and the dashboard uses the PC camera."
            ),
        )

    async def update_runtime(self, request: RuntimeConfigRequest) -> RuntimeStatus:
        if (
            request.runtime_mode == RuntimeMode.LIVE
            and not request.dry_run
            and not request.operator_confirmed
        ):
            raise PermissionError("operator confirmation is required for live non-dry-run mode")

        self.config.runtime_mode = request.runtime_mode
        self.config.dry_run = request.dry_run
        self.config.robot_movement_target = request.robot_movement_target or (
            MovementTarget.PHYSICAL
            if request.runtime_mode == RuntimeMode.LIVE and not request.dry_run
            else MovementTarget.VIRTUAL
        )
        self.config.camera_source = request.camera_source or (
            CameraSource.ROBOT
            if request.runtime_mode == RuntimeMode.LIVE and not request.dry_run
            else CameraSource.PC
        )
        self._sync_adapter_runtime()
        if self.active_runner is not None:
            self.active_runner.config.runtime_mode = request.runtime_mode
            self.active_runner.config.dry_run = request.dry_run
            self.active_runner.mission.runtime_mode = request.runtime_mode
            self.active_runner.mission.dry_run = request.dry_run

        status = self.runtime_status()
        self.event_store.emit(
            self.active_runner.mission.mission_id if self.active_runner else "system-runtime",
            EventType.RUNTIME_CONFIG_UPDATED,
            state=self.active_runner.mission.state if self.active_runner else None,
            robot_id="operator",
            data={
                "request": request.model_dump(mode="json"),
                "runtime": status.model_dump(mode="json"),
            },
        )
        self.restart_cyberwave_movement_feed()
        self.restart_live_vision()
        return status

    def start_live_vision(self) -> None:
        self._live_vision_worker.start()

    def stop_live_vision(self) -> None:
        self._live_vision_worker.stop()

    def restart_live_vision(self) -> None:
        self._live_vision_worker.restart()

    def live_vision_status(self) -> dict:
        return self._live_vision_worker.status()

    def latest_live_vision_frame(self) -> bytes | None:
        return self._live_vision_worker.latest_frame_jpeg()

    def latest_live_vision_result(self) -> dict | None:
        return self._live_vision_worker.latest_result() or self._latest_vision_result

    def ingest_live_vision_result(
        self,
        payload: dict,
        *,
        frame_bytes: bytes,
        robot_id: str,
        frame_id: str,
    ) -> dict:
        detections = payload.get("detections")
        if not isinstance(detections, list):
            detections = []

        classification = self._classification_from_detections(detections)
        result = {
            "frame_id": frame_id,
            "robot_id": robot_id,
            "frame_media_type": "image/jpeg",
            "classification": classification.model_dump(mode="json"),
            "detections": detections,
            "model_id": payload.get("model_id"),
            "valid": bool(detections),
            "validation_errors": [] if detections else ["No detections from live vision loop."],
        }
        result = self._apply_risk_map_update(result, frame_bytes, robot_id=robot_id, frame_id=frame_id)
        self._latest_vision_result = result
        self.event_store.emit(
            self.active_runner.mission.mission_id if self.active_runner else "system-vision",
            EventType.VISION_CLASSIFIED,
            state=self.active_runner.mission.state if self.active_runner else None,
            robot_id=robot_id,
            data={
                "vision": result,
                "detection_count": len(detections),
            },
        )
        return result

    def _classification_from_detections(self, detections: list[dict]) -> ClassificationResult:
        risk_rank = {"DANGER": 3, "AVOID": 2, "SAFE": 1}
        risk_map = {
            "SAFE": (ClassificationLabel.NOT_MINE, RecommendedAction.REPORT),
            "DANGER": (ClassificationLabel.MINE, RecommendedAction.REPORT),
            "AVOID": (ClassificationLabel.UNCERTAIN, RecommendedAction.SECOND_VIEW),
        }
        if not detections:
            return ClassificationResult(
                label=ClassificationLabel.UNCERTAIN,
                confidence=0.0,
                bbox=None,
                evidence=["Live vision loop returned no detections."],
                recommended_action=RecommendedAction.HUMAN_REVIEW,
            )

        target = max(
            detections,
            key=lambda item: (
                risk_rank.get(str(item.get("risk", "")).upper(), 0),
                float(item.get("confidence") or 0.0),
            ),
        )
        risk = str(target.get("risk") or "AVOID").upper()
        label, action = risk_map.get(risk, (ClassificationLabel.UNCERTAIN, RecommendedAction.HUMAN_REVIEW))
        bbox = target.get("bbox")
        if isinstance(bbox, list) and len(bbox) >= 4 and max(bbox) <= 1:
            x, y, w, h = bbox[:4]
            width = int(round(float(w) * 640))
            height = int(round(float(h) * 480))
            left = int(round(float(x) * 640))
            top = int(round(float(y) * 480))
            pixel_bbox = [left, top, left + max(width, 1), top + max(height, 1)]
        else:
            pixel_bbox = bbox if isinstance(bbox, list) else None

        return ClassificationResult(
            label=label,
            confidence=float(target.get("confidence") or 0.0),
            bbox=pixel_bbox,
            evidence=[
                "SENSE = live_vision headless loop (gemini-robotics-er, detect_boxes).",
                f"Colore dominante classificato come {target.get('class')} -> {risk}.",
                f"{len(detections)} oggetti nel frame; scelto il bersaglio più pericoloso.",
            ],
            recommended_action=action,
        )

    def start_cyberwave_movement_feed(self) -> None:
        if not env_bool("SAFEGROUND_CYBERWAVE_MOVEMENT_FEED", True):
            return
        self._movement_feed_started = True
        self._movement_feed_monitor.start()

    def stop_cyberwave_movement_feed(self) -> None:
        self._movement_feed_started = False
        self._movement_feed_monitor.stop()

    def restart_cyberwave_movement_feed(self) -> None:
        if not self._movement_feed_started:
            return
        self._movement_feed_monitor.restart()

    def _movement_feed_mission_id(self) -> str:
        if self.active_runner is not None:
            return self.active_runner.mission.mission_id
        return "system-movement-feed"

    def _resolve_cyberwave_movement_affect_mode(self) -> str:
        if self.config.runtime_mode == RuntimeMode.LIVE and not self.config.dry_run:
            return "live"
        return "simulation"

    def camera_streams(self) -> list[CameraStream]:
        if self.config.camera_source == CameraSource.PC:
            return []
        return self._cyberwave_camera_streams()

    def _cyberwave_camera_streams(self) -> list[CameraStream]:
        path = self.config.cyberwave_config_dir / "camera_streams.json"
        if not path.exists():
            return []
        raw = json.loads(path.read_text(encoding="utf-8"))
        twin_map = raw.get("twin_to_stream_url", {})
        twin_to_robot = {
            "758bee49": "go2",
            "8a40ed9f": "ugv-beast",
            "577e2d72": "so101",
            "33b64f26": "so101-ugv",
        }
        streams: list[CameraStream] = []
        for twin_id, source_url in twin_map.items():
            robot_id = next(
                (robot for prefix, robot in twin_to_robot.items() if twin_id.startswith(prefix)),
                twin_id[:8],
            )
            browser_url = source_url.replace("host.docker.internal", "localhost")
            streams.append(
                CameraStream(
                    twin_id=twin_id,
                    robot_id=robot_id,
                    source_url=source_url,
                    browser_url=browser_url,
                )
            )
        return streams

    def discover_cyberwave_robots(self, *, emit_event: bool = True) -> list[CyberwaveRobot]:
        config_dir = self.config.cyberwave_config_dir
        environment_path = config_dir / "environment.json"
        streams_by_twin = {stream.twin_id: stream for stream in self._cyberwave_camera_streams()}
        robots: list[CyberwaveRobot] = []

        if environment_path.exists():
            raw_environment = json.loads(environment_path.read_text(encoding="utf-8"))
            for twin_uuid in raw_environment.get("twin_uuids", []):
                twin_path = config_dir / f"{twin_uuid}.json"
                if not twin_path.exists():
                    continue
                raw_twin = json.loads(twin_path.read_text(encoding="utf-8"))
                asset = raw_twin.get("asset", {})
                metadata = asset.get("metadata", {})
                registry_id = asset.get("registry_id")
                robot_id = self._robot_id_from_twin(
                    twin_uuid,
                    raw_twin.get("name", ""),
                    registry_id,
                )
                stream = streams_by_twin.get(twin_uuid)
                robots.append(
                    CyberwaveRobot(
                        twin_uuid=twin_uuid,
                        name=raw_twin.get("name") or asset.get("name") or robot_id,
                        robot_id=robot_id,
                        registry_id=registry_id,
                        slug=asset.get("slug"),
                        has_stream=stream is not None,
                        stream_url=stream.source_url if stream else None,
                        browser_url=stream.browser_url if stream else None,
                        available_actions=sorted(
                            metadata.get("mqtt", {}).get("commands", {}).get("supported", [])
                        ),
                    )
                )

        if not robots:
            robots = [
                CyberwaveRobot(
                    twin_uuid=f"mock-{robot_id}",
                    name=status.role,
                    robot_id=robot_id,
                    registry_id=self._cyberwave_twin_slug(robot_id),
                    available_actions=status.actions,
                    source="mock",
                )
                for robot_id, status in self._mock_robot_status_map().items()
            ]

        discovered_ids = {robot.robot_id for robot in robots}
        for robot_id in discovered_ids:
            state = self.robot_activations.setdefault(
                robot_id,
                RobotActivationState(robot_id=robot_id),
            )
            state.available = True
            state.last_check = self._now()
        for robot_id, state in self.robot_activations.items():
            if robot_id not in discovered_ids:
                state.available = False
                state.last_check = self._now()

        if emit_event:
            self.event_store.emit(
                self.active_runner.mission.mission_id if self.active_runner else "system-runtime",
                EventType.CYBERWAVE_ROBOTS_DISCOVERED,
                state=self.active_runner.mission.state if self.active_runner else None,
                robot_id="cyberwave",
                data={"robots": [robot.model_dump(mode="json") for robot in robots]},
            )
        return robots

    async def activate_robot(
        self,
        robot_id: str,
        request: RobotActivationRequest,
    ) -> RobotActivationState:
        if not request.operator_confirmed:
            raise PermissionError("operator confirmation is required before activating a robot")
        discovered = {robot.robot_id for robot in self.discover_cyberwave_robots(emit_event=False)}
        if robot_id not in self.fleet and robot_id not in discovered:
            raise KeyError(robot_id)
        if (
            robot_id not in self.fleet
            and request.activation_mode == RobotActivationMode.ARMED
            and request.allow_physical
        ):
            raise PermissionError("physical arming requires a local SafeGround robot adapter")
        if (
            request.allow_physical
            and request.activation_mode == RobotActivationMode.ARMED
            and (self.config.runtime_mode != RuntimeMode.LIVE or self.config.dry_run)
        ):
            raise PermissionError("physical arming requires live runtime with dry-run disabled")

        state = self.robot_activations.setdefault(
            robot_id,
            RobotActivationState(robot_id=robot_id),
        )
        state.available = robot_id in discovered or robot_id in self.fleet
        state.ready = True
        state.armed = request.activation_mode == RobotActivationMode.ARMED
        state.activation_mode = request.activation_mode
        state.physical_enabled = bool(state.armed and request.allow_physical)
        state.virtual_enabled = True
        state.operator_id = request.operator_id
        state.reason = request.reason
        state.last_check = self._now()

        if robot_id in self.fleet and hasattr(self.fleet[robot_id], "task"):
            self.fleet[robot_id].task = "armed" if state.armed else "ready"

        self.event_store.emit(
            self.active_runner.mission.mission_id if self.active_runner else "system-runtime",
            EventType.ROBOT_ACTIVATION_UPDATED,
            state=self.active_runner.mission.state if self.active_runner else None,
            robot_id=robot_id,
            data={
                "request": request.model_dump(mode="json"),
                "activation": state.model_dump(mode="json"),
            },
        )
        return state

    async def latest_robot_frame(self, robot_id: str) -> tuple[bytes, str]:
        if robot_id not in self.fleet:
            raise KeyError(robot_id)

        frame_bytes = await asyncio.to_thread(self._fetch_latest_robot_frame_sync, robot_id)
        return frame_bytes, self._image_media_type(frame_bytes)

    async def classify_robot_frame(self, robot_id: str) -> dict:
        if robot_id not in self.fleet:
            raise KeyError(robot_id)

        frame_bytes, media_type = await self.latest_robot_frame(robot_id)
        return await self._classify_frame_bytes(
            frame_bytes,
            media_type=media_type,
            robot_id=robot_id,
            source=f"{robot_id}-camera",
        )

    async def classify_image(self, request: ImageClassifyRequest) -> dict:
        payload = request.image_base64.strip()
        if payload.startswith("data:") and "," in payload:
            payload = payload.split(",", 1)[1]
        try:
            frame_bytes = base64.b64decode(payload)
        except (ValueError, binascii.Error) as exc:
            raise RuntimeError("Invalid base64 image payload.") from exc

        media_type = self._image_media_type(frame_bytes)
        return await self._classify_frame_bytes(
            frame_bytes,
            media_type=media_type,
            robot_id=request.robot_id,
            source=request.source,
        )

    async def _classify_frame_bytes(
        self,
        frame_bytes: bytes,
        *,
        media_type: str,
        robot_id: str,
        source: str,
    ) -> dict:
        validated = self._validate_frame_bytes(frame_bytes)
        output_dir = Path("safeground_runs/frames")
        output_dir.mkdir(parents=True, exist_ok=True)
        frame_id = f"{robot_id}-{uuid4().hex[:8]}"
        suffix = ".jpg" if media_type == "image/jpeg" else ".png"
        output_path = output_dir / f"{frame_id}{suffix}"
        output_path.write_bytes(validated)

        frame_ref = FrameRef(
            frame_id=frame_id,
            sensor_id=source,
            source="cyberwave" if robot_id != "pc-camera" else "camera",
            path=output_path,
            metadata={"robot_id": robot_id},
        )
        classification = await self._build_cv_client().classify(frame_ref, "FIELD")
        raw_response = classification.raw_response if isinstance(classification.raw_response, dict) else {}
        detections = raw_response.get("detections", [])
        result = {
            "frame_id": frame_id,
            "robot_id": robot_id,
            "frame_media_type": media_type,
            "frame_base64": base64.b64encode(validated).decode("ascii"),
            "classification": classification.result.model_dump(mode="json"),
            "detections": detections,
            "model_id": raw_response.get("model_id"),
            "valid": classification.valid,
            "validation_errors": classification.validation_errors,
        }
        return self._apply_risk_map_update(result, validated, robot_id=robot_id, frame_id=frame_id)

    def _fetch_latest_robot_frame_sync(self, robot_id: str) -> bytes:
        api_key = os.environ.get("CYBERWAVE_API_KEY")
        if not api_key:
            raise RuntimeError("CYBERWAVE_API_KEY is required to read robot frames.")

        try:
            from cyberwave import Cyberwave
        except ImportError as exc:
            raise RuntimeError("Install cyberwave[camera] to read latest robot frames.") from exc

        environment_id = self._resolve_cyberwave_environment_id()
        twin_ref = self._resolve_cyberwave_twin_ref(robot_id)
        affect_modes = self._cyberwave_affect_modes()
        errors: list[str] = []

        for affect_mode in affect_modes:
            try:
                cw = Cyberwave(api_key=api_key, environment_id=environment_id)
                cw.affect(affect_mode)
                twin = self._open_cyberwave_twin(cw, robot_id, twin_ref, environment_id)
                frame_bytes = self._read_cyberwave_frame_bytes(twin)
                return self._validate_frame_bytes(frame_bytes)
            except RuntimeError as exc:
                errors.append(f"{affect_mode}: {exc}")
            except Exception as exc:  # pragma: no cover - depends on Cyberwave runtime
                errors.append(f"{affect_mode}: {exc}")

        detail = "; ".join(errors) or "No robot frame available."
        raise RuntimeError(detail)

    def _resolve_cyberwave_environment_id(self) -> str | None:
        configured = os.environ.get("CYBERWAVE_ENVIRONMENT")
        if configured:
            return configured

        environment_path = self.config.cyberwave_config_dir / "environment.json"
        if not environment_path.exists():
            return None

        raw_environment = json.loads(environment_path.read_text(encoding="utf-8"))
        return raw_environment.get("uuid") or raw_environment.get("environment_id")

    def _resolve_cyberwave_twin_ref(self, robot_id: str) -> dict[str, str | None]:
        configured_uuid = os.environ.get(
            f"SAFEGROUND_CYBERWAVE_TWIN_UUID_{robot_id.upper().replace('-', '_')}"
        )
        slug = self._cyberwave_twin_slug(robot_id)
        twin_uuid = configured_uuid

        if twin_uuid is None:
            for robot in self.discover_cyberwave_robots(emit_event=False):
                if robot.robot_id == robot_id and not robot.twin_uuid.startswith("mock-"):
                    twin_uuid = robot.twin_uuid
                    slug = robot.slug or robot.registry_id or slug
                    break

        return {"twin_uuid": twin_uuid, "slug": slug}

    def _cyberwave_affect_modes(self) -> list[str]:
        if self.config.runtime_mode == RuntimeMode.LIVE and not self.config.dry_run:
            return ["live", "simulation"]
        return ["simulation", "live"]

    def _open_cyberwave_twin(
        self,
        cw,
        robot_id: str,
        twin_ref: dict[str, str | None],
        environment_id: str | None,
    ):
        twin_uuid = twin_ref.get("twin_uuid")
        slug = twin_ref.get("slug")
        if twin_uuid and environment_id:
            return cw.twin(twin_id=twin_uuid, environment_id=environment_id)
        if twin_uuid:
            return cw.twin(twin_id=twin_uuid)
        if slug:
            return cw.twin(slug)
        raise RuntimeError(f"No Cyberwave twin mapping found for robot {robot_id!r}.")

    def _read_cyberwave_frame_bytes(self, twin) -> bytes | None:
        if hasattr(twin, "get_latest_frame"):
            frame_bytes = twin.get_latest_frame()
            return frame_bytes or None

        for source in ("cloud",):
            try:
                frame_bytes = twin.get_frame(source=source)
            except Exception:
                continue
            if frame_bytes:
                return frame_bytes

        try:
            captured = twin.capture_frame("bytes")
        except Exception:
            captured = None
        if isinstance(captured, (bytes, bytearray)) and captured:
            return bytes(captured)
        return None

    def _validate_frame_bytes(self, frame_bytes: bytes | None) -> bytes:
        if not frame_bytes:
            raise RuntimeError("Cyberwave returned an empty frame.")

        if frame_bytes[:1] == b"{":
            try:
                payload = json.loads(frame_bytes.decode("utf-8"))
            except json.JSONDecodeError as exc:
                raise RuntimeError("Cyberwave returned a non-image payload.") from exc
            detail = payload.get("detail") or payload.get("message") or payload.get("error")
            raise RuntimeError(str(detail or "Cyberwave returned a non-image payload."))

        if self._image_media_type(frame_bytes) not in {
            "image/jpeg",
            "image/png",
            "image/gif",
            "image/webp",
        }:
            raise RuntimeError("Cyberwave returned an unsupported frame format.")
        return frame_bytes

    async def start_object_pickup(
        self,
        request: ObjectPickupStartRequest,
    ) -> ObjectPickupSession:
        if not request.operator_confirmed:
            raise PermissionError("operator confirmation is required before assisted pickup")

        runner = self.active_runner or self._build_runner()
        self.active_runner = runner
        streams = self.camera_streams()
        session = ObjectPickupSession(
            object_label=request.object_label,
            operator_id=request.operator_id,
            camera_streams=streams,
            reason=request.reason,
        )
        low_posture_step = ObjectPickupStep(
            step_type="go2_posture",
            robot_id="go2",
            action="stand_down",
            data={
                "description": "Go2 lowers to ground posture before SO-101 assisted pickup.",
                "safeground_status": "recorded_mock_step",
            },
            camera_streams=streams,
        )
        session.steps.append(low_posture_step)
        go2 = self.fleet.get("go2")
        if go2 is not None and hasattr(go2, "task"):
            go2.task = "low_posture_for_pickup"

        self.active_object_pickup_session = session
        self.object_pickup_sessions.append(session)
        self._persist_object_pickup_sessions()
        self.event_store.emit(
            runner.mission.mission_id,
            EventType.OBJECT_PICKUP_SESSION_STARTED,
            state=runner.mission.state,
            robot_id="go2",
            data=session.model_dump(mode="json"),
        )
        return session

    async def finish_object_pickup(
        self,
        request: ObjectPickupFinishRequest,
    ) -> ObjectPickupSession:
        session = self._object_pickup_session(request.session_id)
        session.status = "saved" if request.save_as_template else "replayed"
        session.finished_at = self._now()
        self.active_object_pickup_session = None
        self._persist_object_pickup_sessions()
        self.event_store.emit(
            self.active_runner.mission.mission_id if self.active_runner else session.session_id,
            EventType.OBJECT_PICKUP_SESSION_FINISHED,
            state=self.active_runner.mission.state if self.active_runner else None,
            robot_id="so101",
            data={
                "request": request.model_dump(mode="json"),
                "session": session.model_dump(mode="json"),
            },
        )
        return session

    async def replay_object_pickup(
        self,
        request: ObjectPickupReplayRequest,
    ) -> ObjectPickupSession:
        if not request.operator_confirmed:
            raise PermissionError("operator confirmation is required before replaying a pickup template")

        session = self._object_pickup_session(request.session_id)
        session.replay_count += 1
        self._persist_object_pickup_sessions()
        self.event_store.emit(
            self.active_runner.mission.mission_id if self.active_runner else session.session_id,
            EventType.OBJECT_PICKUP_TEMPLATE_REPLAYED,
            state=self.active_runner.mission.state if self.active_runner else None,
            robot_id="so101",
            data={
                "request": request.model_dump(mode="json"),
                "session": session.model_dump(mode="json"),
                "automation_status": "manual template selected; no autonomous YOLO execution yet",
            },
        )
        return session

    async def start_mission(self, scenario: str = "FIELD") -> MissionReport:
        runner = self._build_runner()
        self.active_runner = runner
        report = await runner.run(scenario)
        self.latest_report = report
        return report

    async def mark_latest_object(self, request: ObjectMarkRequest) -> MissionReport:
        if self.latest_report is None or not self.latest_report.observations:
            raise PermissionError("No camera observation is available to mark.")

        report = self.latest_report
        latest_observation = report.observations[-1]
        marked_result = ClassificationResult(
            label=request.label,
            confidence=1.0,
            bbox=latest_observation.classification.bbox,
            evidence=[
                *latest_observation.classification.evidence,
                f"Operator {request.operator_id} marked object as {request.label}.",
            ],
            recommended_action=(
                RecommendedAction.SECOND_VIEW
                if request.label == ClassificationLabel.UNCERTAIN
                else RecommendedAction.REPORT
            ),
        )
        latest_observation.classification = marked_result
        report.classification = marked_result
        report.recommendation = marked_result.recommended_action
        report.safe_to_contact = request.label == ClassificationLabel.NOT_MINE
        report.summary = f"Operator marked latest camera object as {request.label}."
        report.finding = Finding(
            mission_id=report.mission_id,
            label=request.label,
            confidence=marked_result.confidence,
            safe_to_contact=report.safe_to_contact,
            observations=[observation.observation_id for observation in report.observations],
            rationale=request.reason,
        )

        mission = self.active_runner.mission if self.active_runner else None
        self.event_store.emit(
            report.mission_id,
            EventType.OBJECT_MARKED,
            state=mission.state if mission else report.state,
            robot_id=latest_observation.robot_id,
            sensor_id=latest_observation.sensor_id,
            frame_path=latest_observation.frame.path,
            data={
                "request": request.model_dump(mode="json"),
                "classification": marked_result.model_dump(mode="json"),
                "finding": report.finding.model_dump(mode="json"),
            },
        )
        return report

    async def stop_all(self) -> MissionReport:
        runner = self.active_runner or self._build_runner()
        report = await runner.stop()
        self.latest_report = report
        return report

    async def stop_robot(self, robot_id: str) -> list[RobotStatus]:
        if robot_id not in self.fleet:
            raise KeyError(robot_id)

        robot = self.fleet[robot_id]
        self.event_store.emit(
            self.active_runner.mission.mission_id if self.active_runner else "system-movement",
            EventType.ROBOT_STOP_REQUESTED,
            state=self.active_runner.mission.state if self.active_runner else None,
            robot_id=robot_id,
            data={"reason": "Operator requested robot stop from UI."},
        )
        await robot.stop()
        if robot_id == self.movement_controller.robot_id:
            self._transition_movement(
                MovementFSMState.STOPPED,
                robot_id=robot_id,
                reason="Operator stopped robot movement.",
            )
        self.event_store.emit(
            self.active_runner.mission.mission_id if self.active_runner else "system-movement",
            EventType.ROBOT_STOPPED,
            state=self.active_runner.mission.state if self.active_runner else None,
            robot_id=robot_id,
            data={"status": (await robot.status()).model_dump(mode="json")},
        )
        return await self.robot_statuses()

    async def manual_arm_takeover(
        self,
        robot_id: str,
        command: ManualArmCommand,
    ) -> ManualArmResult:
        runner = self.active_runner or self._build_runner()
        self.active_runner = runner
        robot = self.fleet[robot_id]

        self.event_store.emit(
            runner.mission.mission_id,
            EventType.MANUAL_ARM_COMMAND_REQUESTED,
            state=runner.mission.state,
            robot_id=robot.id,
            data=command.model_dump(mode="json"),
        )
        await runner._transition(MissionState.MANUAL_TAKEOVER)
        result = await runner.safety.run_manual_arm_checked(
            runner.mission,
            robot.id,
            command,
            lambda: robot.execute_manual_arm_command(command),
        )
        self.event_store.emit(
            runner.mission.mission_id,
            EventType.MANUAL_ARM_COMMAND_APPLIED,
            state=runner.mission.state,
            robot_id=robot.id,
            data=result.model_dump(mode="json"),
        )
        self._record_object_pickup_arm_step(runner, command, result)
        return result

    async def move_robot_base(
        self,
        robot_id: str,
        command: BaseMovementCommand,
    ) -> BaseMovementResult:
        runner = self.active_runner or self._build_runner()
        self.active_runner = runner
        robot = self.fleet[robot_id]
        command = self._resolve_base_movement_target(robot_id, command)

        self.event_store.emit(
            runner.mission.mission_id,
            EventType.BASE_MOVEMENT_COMMAND_REQUESTED,
            state=runner.mission.state,
            robot_id=robot.id,
            data=command.model_dump(mode="json"),
        )
        await runner._transition(MissionState.MANUAL_TAKEOVER)
        result = await runner.safety.run_base_movement_checked(
            runner.mission,
            robot.id,
            command,
            lambda: robot.execute_base_movement(command),
        )
        if result.virtual_applied:
            result.executed_sequence.append(
                self._sync_virtual_cyberwave_pose(robot.id, result.pose)
            )
        self.event_store.emit(
            runner.mission.mission_id,
            EventType.BASE_MOVEMENT_COMMAND_APPLIED,
            state=runner.mission.state,
            robot_id=robot.id,
            data=result.model_dump(mode="json"),
        )
        return result

    async def run_movement_command(
        self,
        request: MovementCommandRequest,
    ) -> MovementCommandResult:
        if request.robot_id != "go2":
            raise PermissionError("LLM-assisted movement is restricted to Unitree Go2.")
        if request.robot_id not in self.fleet:
            raise KeyError(request.robot_id)

        self._transition_movement(
            MovementFSMState.PLANNING,
            robot_id=request.robot_id,
            reason="Operator submitted movement text.",
        )
        self.event_store.emit(
            self.active_runner.mission.mission_id if self.active_runner else "system-movement",
            EventType.MOVEMENT_COMMAND_RECEIVED,
            state=self.active_runner.mission.state if self.active_runner else None,
            robot_id=request.robot_id,
            data=request.model_dump(mode="json"),
        )

        plan = MovementCommandAgent().plan(request)
        self.event_store.emit(
            self.active_runner.mission.mission_id if self.active_runner else "system-movement",
            EventType.MOVEMENT_AGENT_DECISION_MADE,
            state=self.active_runner.mission.state if self.active_runner else None,
            robot_id=request.robot_id,
            data=plan.model_dump(mode="json"),
        )
        if not plan.accepted or plan.command is None:
            self._transition_movement(
                MovementFSMState.REJECTED,
                robot_id=request.robot_id,
                plan=plan,
                reason=plan.reason,
            )
            return MovementCommandResult(
                state=self.movement_controller.state,
                plan=plan,
                reason=plan.reason,
            )

        self._transition_movement(
            MovementFSMState.PLANNED,
            robot_id=request.robot_id,
            plan=plan,
            reason=plan.reason,
        )
        self._transition_movement(
            MovementFSMState.SAFETY_CHECKED,
            robot_id=request.robot_id,
            plan=plan,
            reason="Movement command will run through the SafetyGovernor.",
        )
        self._transition_movement(
            MovementFSMState.EXECUTING,
            robot_id=request.robot_id,
            plan=plan,
            reason="Executing one bounded movement command.",
        )
        try:
            result = await self.move_robot_base(request.robot_id, plan.command)
        except PermissionError as exc:
            self._transition_movement(
                MovementFSMState.REJECTED,
                robot_id=request.robot_id,
                plan=plan,
                reason=str(exc),
            )
            raise

        self._transition_movement(
            MovementFSMState.COMPLETED,
            robot_id=request.robot_id,
            plan=plan,
            result=result,
            reason="Movement command completed.",
        )
        return MovementCommandResult(
            state=self.movement_controller.state,
            plan=plan,
            result=result,
            reason=self.movement_controller.reason,
        )

    async def plan_scout_route(self, command: ScoutRouteCommand) -> ScoutRouteResult:
        runner = self.active_runner or self._build_runner()
        self.active_runner = runner
        if command.robot_id != "go2":
            raise PermissionError("P0 scout route planning is restricted to Unitree Go2.")
        if not command.operator_confirmed:
            raise PermissionError("operator confirmation is required before planning a scout route")

        obstacles = [
            MapObstacle(label="mock obstacle", position=MapPoint(x=0.62, y=0.38), radius=0.07),
            MapObstacle(label="uncertain target zone", position=MapPoint(x=0.42, y=0.58), radius=0.06),
        ]
        point_map = [*command.waypoints, *[obstacle.position for obstacle in obstacles]]
        result = ScoutRouteResult(
            robot_id=command.robot_id,
            accepted=True,
            dry_run=self.config.dry_run,
            waypoints=command.waypoints,
            point_map=point_map,
            obstacles=obstacles,
            reason=command.reason,
        )
        self.latest_scout_route = result
        self.event_store.emit(
            runner.mission.mission_id,
            EventType.SCOUT_ROUTE_PLANNED,
            state=runner.mission.state,
            robot_id=command.robot_id,
            data=result.model_dump(mode="json"),
        )
        self.event_store.emit(
            runner.mission.mission_id,
            EventType.POINT_MAP_UPDATED,
            state=runner.mission.state,
            robot_id=command.robot_id,
            data={
                "point_map": [point.model_dump(mode="json") for point in point_map],
                "obstacles": [obstacle.model_dump(mode="json") for obstacle in obstacles],
            },
        )
        return result

    async def run_command(self, request: CommandRequest) -> MissionReport:
        text = request.text or ""
        runner = self._build_runner()
        self.active_runner = runner
        self.event_store.emit(
            runner.mission.mission_id,
            EventType.USER_COMMAND_RECEIVED,
            state=runner.mission.state,
            robot_id=runner.robot.id,
            data={"text": text, "target_sector": request.target_sector},
        )
        intent = OperatorCommandAgent().parse(text)
        self.event_store.emit(
            runner.mission.mission_id,
            EventType.AGENT_INTENT_PARSED,
            state=runner.mission.state,
            robot_id=runner.robot.id,
            data=intent.model_dump(mode="json"),
        )
        decision = OrchestratorAgent(self.config).decide(intent)
        self.event_store.emit(
            runner.mission.mission_id,
            EventType.AGENT_DECISION_MADE,
            state=runner.mission.state,
            robot_id=runner.robot.id,
            data=decision.model_dump(mode="json"),
        )

        if decision.decision == AgentDecisionType.STOP_ALL:
            report = await runner.stop()
        elif decision.decision == AgentDecisionType.REPORT_STATUS:
            await runner._record_robot_status()
            report = runner._build_report(summary="Status reported; no mission was started.")
        elif decision.decision == AgentDecisionType.RUN_MISSION:
            report = await runner.run(
                decision.scenario_hint or request.scenario,
                target_sector=decision.target_sector or request.target_sector,
            )
        else:
            report = runner._build_report(
                summary="Command requires human review; no mission was started."
            )
        self.latest_report = report
        return report

    def events(self, limit: int | None = 200) -> list[Event]:
        in_memory = self.event_store.list_events(limit=limit)
        if in_memory:
            return in_memory
        return self.event_store.load_from_disk(limit=limit)

    async def snapshot(self) -> MissionSnapshot:
        return MissionSnapshot(
            mission=self.active_runner.mission if self.active_runner else None,
            runtime=self.runtime_status(),
            report=self.latest_report,
            robots=await self.robot_statuses(),
            events=[event.model_dump(mode="json") for event in self.events(limit=100)],
            camera_streams=self.camera_streams(),
            cyberwave_robots=self.discover_cyberwave_robots(emit_event=False),
            robot_activations=list(self.robot_activations.values()),
            movement_controller=self.movement_controller,
            scout_route=self.latest_scout_route,
            object_pickup_sessions=self.object_pickup_sessions,
            active_object_pickup_session=self.active_object_pickup_session,
            risk_map=self.risk_map_state(),
        )

    def risk_map_state(self) -> RiskMapState:
        return RiskMapState.model_validate(self.risk_map_grid.to_dict())

    def clear_risk_map(self) -> RiskMapState:
        self.risk_map_grid.clear()
        state = self.risk_map_state()
        self.event_store.emit(
            self.active_runner.mission.mission_id if self.active_runner else "system-risk-map",
            EventType.RISK_MAP_UPDATED,
            state=self.active_runner.mission.state if self.active_runner else None,
            robot_id=state.observer_robot_id,
            data={"risk_map": state.model_dump(mode="json"), "cleared": True},
        )
        return state

    def _build_risk_map_grid(self):
        live_vision_dir = Path(__file__).resolve().parents[2] / "live_vision"
        if live_vision_dir.exists() and str(live_vision_dir) not in sys.path:
            sys.path.insert(0, str(live_vision_dir))
        from risk_map import RiskMapGrid

        return RiskMapGrid()

    def _frame_dimensions(self, frame_bytes: bytes) -> tuple[int, int]:
        try:
            import cv2
            import numpy as np

            image = cv2.imdecode(np.frombuffer(frame_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
            if image is not None:
                height, width = image.shape[:2]
                return width, height
        except ImportError:
            pass
        return 640, 480

    def _apply_risk_map_update(
        self,
        result: dict,
        frame_bytes: bytes,
        *,
        robot_id: str,
        frame_id: str,
    ) -> dict:
        width, height = self._frame_dimensions(frame_bytes)
        detections = result.get("detections")
        if not isinstance(detections, list):
            detections = []
        self.risk_map_grid.update(
            detections,
            width=width,
            height=height,
            robot_id=robot_id,
            frame_id=frame_id,
        )
        risk_map = self.risk_map_state()
        result["risk_map"] = risk_map.model_dump(mode="json")
        self.event_store.emit(
            self.active_runner.mission.mission_id if self.active_runner else "system-risk-map",
            EventType.RISK_MAP_UPDATED,
            state=self.active_runner.mission.state if self.active_runner else None,
            robot_id=robot_id,
            data={
                "risk_map": risk_map.model_dump(mode="json"),
                "detection_count": len(detections),
            },
        )
        return result

    def _build_cv_client(self):
        if env_bool("SAFEGROUND_USE_VLM", True):
            live_vision_dir = Path(__file__).resolve().parents[2] / "live_vision"
            if live_vision_dir.exists() and str(live_vision_dir) not in sys.path:
                sys.path.insert(0, str(live_vision_dir))
            try:
                from cv_safeground import CyberwaveVLMClient

                return CyberwaveVLMClient()
            except ImportError:
                pass
        return MockCVClient(self.config)

    def _build_runner(self) -> MissionRunner:
        self._sync_adapter_runtime()
        robot = self._primary_robot()
        cv_client = self._build_cv_client()
        safety = SafetyGovernor(self.config, self.event_store)
        return MissionRunner(
            self.config,
            robot,
            cv_client,
            self.event_store,
            safety,
            fleet=self.fleet,
        )

    def _primary_robot(self) -> RobotAdapter:
        return self.fleet.get(self.config.robot_id) or self.fleet["go2"]

    def _sync_adapter_runtime(self) -> None:
        for robot in self.fleet.values():
            if hasattr(robot, "runtime_mode"):
                robot.runtime_mode = self.config.runtime_mode
            if hasattr(robot, "dry_run"):
                robot.dry_run = self.config.dry_run

    def _transition_movement(
        self,
        state: MovementFSMState,
        *,
        robot_id: str,
        plan: MovementAgentPlan | None = None,
        result: BaseMovementResult | None = None,
        reason: str,
    ) -> None:
        previous = self.movement_controller.state
        self.movement_controller = MovementControllerState(
            state=state,
            robot_id=robot_id,
            last_plan=plan or self.movement_controller.last_plan,
            last_result=result or self.movement_controller.last_result,
            reason=reason,
        )
        self.event_store.emit(
            self.active_runner.mission.mission_id if self.active_runner else "system-movement",
            EventType.MOVEMENT_STATE_CHANGED,
            state=self.active_runner.mission.state if self.active_runner else None,
            robot_id=robot_id,
            data={
                "from": previous,
                "to": state,
                "controller": self.movement_controller.model_dump(mode="json"),
            },
        )

    def _resolve_base_movement_target(
        self,
        robot_id: str,
        command: BaseMovementCommand,
    ) -> BaseMovementCommand:
        target = command.movement_target
        if target == MovementTarget.AUTO:
            target = self.config.robot_movement_target

        wants_physical = target in {MovementTarget.PHYSICAL, MovementTarget.BOTH}
        if wants_physical:
            activation = self.robot_activations.get(robot_id)
            if self.config.runtime_mode != RuntimeMode.LIVE or self.config.dry_run:
                raise PermissionError("physical movement requires live runtime with dry-run disabled")
            if activation is None or not activation.armed or not activation.physical_enabled:
                raise PermissionError("physical movement requires an armed robot")

        return command.model_copy(update={"movement_target": target})

    def _sync_virtual_cyberwave_pose(self, robot_id: str, pose) -> str:
        if not self.config.cyberwave_virtual_sync:
            return "virtual_pose:cyberwave_sync_disabled"
        if self.config.runtime_mode == RuntimeMode.MOCK:
            return "virtual_pose:mock_local_only"

        try:
            from cyberwave import Cyberwave
        except ImportError:
            return "virtual_pose:cyberwave_sdk_unavailable"

        try:
            api_key = os.environ.get("CYBERWAVE_API_KEY")
            environment_id = os.environ.get("CYBERWAVE_ENVIRONMENT")
            kwargs = {}
            if api_key:
                kwargs["api_key"] = api_key
            if environment_id:
                kwargs["environment_id"] = environment_id
            cw = Cyberwave(**kwargs)
            cw.affect("simulation")
            twin = cw.twin(self._cyberwave_twin_slug(robot_id))
            twin.edit_position(x=pose.x, y=pose.y, z=0.0)
            twin.edit_rotation(yaw=math.degrees(pose.yaw))
        except Exception as exc:  # pragma: no cover - depends on local Cyberwave runtime
            return f"virtual_pose:cyberwave_sync_failed:{exc}"

        return "virtual_pose:cyberwave_simulation_synced"

    def _cyberwave_twin_slug(self, robot_id: str) -> str:
        env_name = f"SAFEGROUND_CYBERWAVE_TWIN_{robot_id.upper().replace('-', '_')}"
        configured_slug = os.environ.get(env_name)
        if configured_slug:
            return configured_slug

        return {
            "go2": "unitree/go2",
            "ugv-beast": "waveshare/ugv-beast",
            "so101": "the-robot-studio/so101",
            "so101-ugv": "the-robot-studio/so101",
            "fixed-camera": "cyberwave/standard-cam",
        }[robot_id]

    def _robot_id_from_twin(
        self,
        twin_uuid: str,
        name: str,
        registry_id: str | None,
    ) -> str:
        uuid_map = {
            "758bee49": "go2",
            "8a40ed9f": "ugv-beast",
            "577e2d72": "so101",
            "33b64f26": "so101-ugv",
        }
        for prefix, robot_id in uuid_map.items():
            if twin_uuid.startswith(prefix):
                return robot_id
        normalized = f"{name} {registry_id or ''}".lower()
        if "go2" in normalized:
            return "go2"
        if "ugv" in normalized:
            return "ugv-beast"
        if "so-101" in normalized or "so101" in normalized:
            return "so101"
        return twin_uuid[:8]

    def _mock_robot_status_map(self) -> dict[str, RobotStatus]:
        return {
            robot_id: RobotStatus(
                robot_id=robot_id,
                role=getattr(robot, "role", robot_id),
                mode=self.config.runtime_mode,
                task=getattr(robot, "task", "idle"),
                battery_percent=getattr(robot, "battery_percent", None),
                sensors=getattr(robot, "sensors", []),
                actions=getattr(robot, "actions", []),
                pose=getattr(robot, "pose"),
                note=getattr(robot, "note", None),
            )
            for robot_id, robot in self.fleet.items()
        }

    def _image_media_type(self, frame_bytes: bytes) -> str:
        if frame_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if frame_bytes.startswith(b"GIF"):
            return "image/gif"
        if frame_bytes.startswith(b"RIFF") and frame_bytes[8:12] == b"WEBP":
            return "image/webp"
        return "image/jpeg"

    def _record_object_pickup_arm_step(
        self,
        runner: MissionRunner,
        command: ManualArmCommand,
        result: ManualArmResult,
    ) -> None:
        session = self.active_object_pickup_session
        if session is None or session.status != "recording":
            return
        step = ObjectPickupStep(
            step_type="so101_manual_arm",
            robot_id=result.robot_id,
            action=result.action,
            data={
                "command": command.model_dump(mode="json"),
                "result": result.model_dump(mode="json"),
            },
            camera_streams=self.camera_streams(),
        )
        session.steps.append(step)
        session.camera_streams = step.camera_streams or session.camera_streams
        self._persist_object_pickup_sessions()
        self.event_store.emit(
            runner.mission.mission_id,
            EventType.OBJECT_PICKUP_STEP_RECORDED,
            state=runner.mission.state,
            robot_id=result.robot_id,
            data={
                "session_id": session.session_id,
                "step": step.model_dump(mode="json"),
            },
        )

    def _object_pickup_session(self, session_id: str | None) -> ObjectPickupSession:
        if session_id is None and self.active_object_pickup_session is not None:
            return self.active_object_pickup_session
        for session in self.object_pickup_sessions:
            if session.session_id == session_id:
                return session
        raise PermissionError("object pickup session not found")

    def _object_pickup_store_path(self) -> Path:
        return self.config.event_log_path.parent / "object_pickup_sessions.json"

    def _load_object_pickup_sessions(self) -> None:
        path = self._object_pickup_store_path()
        if not path.exists():
            return
        raw = json.loads(path.read_text(encoding="utf-8"))
        self.object_pickup_sessions = [
            ObjectPickupSession.model_validate(item)
            for item in raw
        ]
        self.active_object_pickup_session = next(
            (session for session in self.object_pickup_sessions if session.status == "recording"),
            None,
        )

    def _persist_object_pickup_sessions(self) -> None:
        path = self._object_pickup_store_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                [session.model_dump(mode="json") for session in self.object_pickup_sessions],
                indent=2,
                ensure_ascii=True,
            ),
            encoding="utf-8",
        )

    def _now(self) -> datetime:
        return datetime.now(UTC)
