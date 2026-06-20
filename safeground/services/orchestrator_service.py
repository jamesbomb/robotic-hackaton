from __future__ import annotations

import json
from pathlib import Path

from safeground.adapters import RobotAdapter, build_mock_fleet
from safeground.agents import OperatorCommandAgent, OrchestratorAgent
from safeground.cv import MockCVClient
from safeground.event_store import Event, JsonlEventStore
from safeground.mission import MissionRunner
from safeground.models import (
    AgentDecisionType,
    BaseMovementCommand,
    BaseMovementResult,
    CameraStream,
    ClassificationLabel,
    ClassificationResult,
    CommandRequest,
    EventType,
    Finding,
    ManualArmCommand,
    ManualArmResult,
    MapObstacle,
    MapPoint,
    MissionReport,
    MissionSnapshot,
    MissionState,
    ObjectMarkRequest,
    RecommendedAction,
    RobotStatus,
    RuntimeConfigRequest,
    RuntimeMode,
    RuntimeStatus,
    SafeGroundConfig,
    ScoutRouteCommand,
    ScoutRouteResult,
)
from safeground.safety import SafetyGovernor


class OrchestratorService:
    def __init__(self, config: SafeGroundConfig | None = None) -> None:
        self.config = config or SafeGroundConfig()
        self.event_store = JsonlEventStore(self.config.event_log_path)
        self.fleet = build_mock_fleet(self.config)
        self.latest_report: MissionReport | None = None
        self.latest_scout_route: ScoutRouteResult | None = None
        self.active_runner: MissionRunner | None = None
        self._sync_adapter_runtime()

    async def robot_statuses(self) -> list[RobotStatus]:
        return [await robot.status() for robot in self.fleet.values()]

    def runtime_status(self) -> RuntimeStatus:
        return RuntimeStatus(
            runtime_mode=self.config.runtime_mode,
            dry_run=self.config.dry_run,
            live_adapter_ready=self.config.runtime_mode == RuntimeMode.LIVE and not self.config.dry_run,
            note=(
                "Live MQTT command bridge is enabled; controller policy topic and broker "
                "must be validated before moving hardware."
                if self.config.runtime_mode == RuntimeMode.LIVE
                else "Mock/simulation-safe adapters are active."
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
        return status

    def camera_streams(self) -> list[CameraStream]:
        path = Path.home() / ".cyberwave" / "camera_streams.json"
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
        return result

    async def move_robot_base(
        self,
        robot_id: str,
        command: BaseMovementCommand,
    ) -> BaseMovementResult:
        runner = self.active_runner or self._build_runner()
        self.active_runner = runner
        robot = self.fleet[robot_id]

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
        self.event_store.emit(
            runner.mission.mission_id,
            EventType.BASE_MOVEMENT_COMMAND_APPLIED,
            state=runner.mission.state,
            robot_id=robot.id,
            data=result.model_dump(mode="json"),
        )
        return result

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
            scout_route=self.latest_scout_route,
        )

    def _build_runner(self) -> MissionRunner:
        self._sync_adapter_runtime()
        robot = self._primary_robot()
        cv_client = MockCVClient(self.config)
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
