from __future__ import annotations

from datetime import UTC, datetime

from safeground.adapters import MockRobotAdapter, RobotAdapter
from safeground.agents import VerificationScoutAgent
from safeground.cv import MockCVClient
from safeground.event_store import JsonlEventStore
from safeground.models import (
    CVClassification,
    ClassificationLabel,
    ClassificationResult,
    EventType,
    Finding,
    FrameRef,
    Mission,
    MissionReport,
    MissionState,
    Observation,
    RecommendedAction,
    RobotPose,
    RoutePoint,
    RouteSafetyStatus,
    RouteTrace,
    SafeGroundConfig,
)
from safeground.safety import SafetyGovernor


class MissionRunner:
    def __init__(
        self,
        config: SafeGroundConfig,
        robot: RobotAdapter,
        cv_client: MockCVClient,
        event_store: JsonlEventStore,
        safety: SafetyGovernor,
        fleet: dict[str, RobotAdapter] | None = None,
    ) -> None:
        self.config = config
        self.robot = robot
        self.cv_client = cv_client
        self.event_store = event_store
        self.safety = safety
        self.fleet = fleet or {robot.id: robot}
        self.mission = Mission(runtime_mode=config.runtime_mode, dry_run=config.dry_run)
        self.frame: FrameRef | None = None
        self.classification: CVClassification | None = None
        self.observations: list[Observation] = []
        self.finding: Finding | None = None
        self.route_trace: RouteTrace | None = None

    async def run(self, scenario: str, target_sector: str | None = None) -> MissionReport:
        self.event_store.emit(
            self.mission.mission_id,
            EventType.MISSION_STARTED,
            state=self.mission.state,
            robot_id=self.robot.id,
            sensor_id=self.config.sensor_id,
            data={
                "runtime_mode": self.config.runtime_mode,
                "dry_run": self.config.dry_run,
                "scenario": scenario.upper(),
                "target_sector": target_sector,
            },
        )

        try:
            await self._record_robot_status()
            await self._transition(MissionState.OBSERVE)
            self.route_trace = self._record_route_trace(target_sector)
            self.frame = await self.safety.run_checked(
                self.mission,
                "capture_frame",
                lambda: self.robot.capture_frame(self.config.sensor_id),
            )
            self.event_store.emit(
                self.mission.mission_id,
                EventType.FRAME_CAPTURED,
                state=self.mission.state,
                robot_id=self.robot.id,
                sensor_id=self.frame.sensor_id,
                frame_path=self.frame.path,
                data=self.frame.model_dump(mode="json"),
            )

            if self.safety.stop_requested:
                return await self.stop()

            await self._transition(MissionState.CLASSIFY)
            self.classification = await self.cv_client.classify(self.frame, scenario)
            self._record_cv_result(self.classification)
            self._record_observation(self.robot, self.frame, self.classification.result)
            self._validate_route_against_classification(self.classification.result)

            if self.safety.stop_requested:
                return await self.stop()

            if self._needs_second_observation(self.classification):
                await self._run_second_observation()

            await self._transition(MissionState.REPORT)
            report = self._build_report()
            self.event_store.emit(
                self.mission.mission_id,
                EventType.MISSION_REPORTED,
                state=self.mission.state,
                robot_id=self.robot.id,
                sensor_id=self.config.sensor_id,
                frame_path=self.frame.path,
                data=report.model_dump(mode="json"),
            )
            return report
        except Exception as exc:
            return await self._error_safe(exc)

    async def stop(self) -> MissionReport:
        self.safety.request_stop()
        await self._transition(MissionState.MANUAL_STOP)
        await self.safety.run_checked(self.mission, "stop", self.robot.stop)
        self.mission.stopped_at = datetime.now(UTC)
        report = self._build_report(summary="Mission stopped by operator.")
        self.event_store.emit(
            self.mission.mission_id,
            EventType.MISSION_STOPPED,
            state=self.mission.state,
            robot_id=self.robot.id,
            data=report.model_dump(mode="json"),
        )
        return report

    async def _record_robot_status(self) -> None:
        for robot in self.fleet.values():
            health = await robot.health()
            capabilities = await robot.capabilities()
            status = await robot.status()
            self.event_store.emit(
                self.mission.mission_id,
                EventType.ROBOT_STATUS_UPDATED,
                state=self.mission.state,
                robot_id=robot.id,
                sensor_id=robot.sensor_id,
                data={
                    "health": health,
                    "capabilities": capabilities,
                    "status": status.model_dump(mode="json"),
                },
            )

    async def _transition(self, state: MissionState) -> None:
        previous = self.mission.state
        self.mission.state = state
        self.event_store.emit(
            self.mission.mission_id,
            EventType.STATE_CHANGED,
            state=self.mission.state,
            robot_id=self.robot.id,
            data={"from": previous, "to": state},
        )

    def _record_cv_result(self, classification: CVClassification) -> None:
        assert self.frame is not None
        self.event_store.emit(
            self.mission.mission_id,
            EventType.CV_RESULT_RECEIVED,
            state=self.mission.state,
            robot_id=self.robot.id,
            sensor_id=self.frame.sensor_id,
            frame_path=self.frame.path,
            data={"raw_response": classification.raw_response},
        )
        self.event_store.emit(
            self.mission.mission_id,
            EventType.CV_RESULT_VALIDATED,
            state=self.mission.state,
            robot_id=self.robot.id,
            sensor_id=self.frame.sensor_id,
            frame_path=self.frame.path,
            data=classification.model_dump(mode="json"),
        )

    def _record_observation(
        self,
        robot: RobotAdapter,
        frame: FrameRef,
        classification: ClassificationResult,
    ) -> Observation:
        observation = Observation(
            mission_id=self.mission.mission_id,
            robot_id=robot.id,
            sensor_id=frame.sensor_id,
            frame=frame,
            classification=classification,
            pose=robot.pose if hasattr(robot, "pose") else RobotPose(),
        )
        self.observations.append(observation)
        self.event_store.emit(
            self.mission.mission_id,
            EventType.OBSERVATION_RECORDED,
            state=self.mission.state,
            robot_id=robot.id,
            sensor_id=frame.sensor_id,
            frame_path=frame.path,
            data=observation.model_dump(mode="json"),
        )
        return observation

    def _record_route_trace(self, target_sector: str | None) -> RouteTrace:
        route = RouteTrace(
            mission_id=self.mission.mission_id,
            robot_id=self.robot.id,
            points=[
                RoutePoint(
                    sector="START",
                    pose=RobotPose(),
                    note="mission start",
                ),
                RoutePoint(
                    sector=target_sector,
                    pose=self.robot.pose if hasattr(self.robot, "pose") else RobotPose(),
                    note="primary observation pose",
                    over_hazard=self.config.route_over_mine,
                ),
            ],
            reusable_by=[
                robot_id
                for robot_id in self.fleet
                if robot_id != self.robot.id and robot_id.lower() not in {"so101", "so-101"}
            ],
        )
        self.event_store.emit(
            self.mission.mission_id,
            EventType.ROUTE_RECORDED,
            state=self.mission.state,
            robot_id=self.robot.id,
            data=route.model_dump(mode="json"),
        )
        return route

    def _validate_route_against_classification(self, result: ClassificationResult) -> None:
        if self.route_trace is None:
            return
        is_mobile_robot = self.robot.id.lower() not in {"so101", "so-101"}
        route_over_hazard = any(point.over_hazard for point in self.route_trace.points)
        if is_mobile_robot and route_over_hazard and result.label == ClassificationLabel.MINE:
            self.route_trace.status = RouteSafetyStatus.UNSAFE
            self.route_trace.reusable_by = []
            self.route_trace.invalidation_reason = (
                "Mobile robot route intersects a sector classified as MINE."
            )
            self.event_store.emit(
                self.mission.mission_id,
                EventType.ROUTE_INVALIDATED,
                state=self.mission.state,
                robot_id=self.robot.id,
                data=self.route_trace.model_dump(mode="json"),
            )

    def _needs_second_observation(self, classification: CVClassification) -> bool:
        result = classification.result
        return (
            result.label == ClassificationLabel.UNCERTAIN
            or result.recommended_action == RecommendedAction.SECOND_VIEW
        )

    async def _run_second_observation(self) -> None:
        verifier_id = VerificationScoutAgent().assign(
            [await robot.status() for robot in self.fleet.values()],
            self.robot.id,
        )
        if verifier_id is None:
            await self._transition(MissionState.HUMAN_REVIEW)
            return
        if self.route_trace is None or self.route_trace.status != RouteSafetyStatus.SAFE:
            await self._transition(MissionState.HUMAN_REVIEW)
            return

        verifier = self.fleet[verifier_id]
        self.event_store.emit(
            self.mission.mission_id,
            EventType.ROUTE_REUSED_FOR_VERIFICATION,
            state=self.mission.state,
            robot_id=verifier.id,
            data={
                "route_id": self.route_trace.route_id,
                "source_robot_id": self.route_trace.robot_id,
                "assigned_robot_id": verifier.id,
                "route": self.route_trace.model_dump(mode="json"),
            },
        )
        await self._transition(MissionState.UNCERTAIN)
        await self._transition(MissionState.SECOND_OBSERVATION)
        second_frame = await self.safety.run_checked(
            self.mission,
            "capture_frame",
            lambda: verifier.capture_frame(verifier.sensor_id),
        )
        self.event_store.emit(
            self.mission.mission_id,
            EventType.FRAME_CAPTURED,
            state=self.mission.state,
            robot_id=verifier.id,
            sensor_id=second_frame.sensor_id,
            frame_path=second_frame.path,
            data=second_frame.model_dump(mode="json"),
        )
        second_classification = await self.cv_client.classify(
            second_frame,
            self.config.verification_scenario,
        )
        self.event_store.emit(
            self.mission.mission_id,
            EventType.CV_RESULT_RECEIVED,
            state=self.mission.state,
            robot_id=verifier.id,
            sensor_id=second_frame.sensor_id,
            frame_path=second_frame.path,
            data={"raw_response": second_classification.raw_response},
        )
        self.event_store.emit(
            self.mission.mission_id,
            EventType.CV_RESULT_VALIDATED,
            state=self.mission.state,
            robot_id=verifier.id,
            sensor_id=second_frame.sensor_id,
            frame_path=second_frame.path,
            data=second_classification.model_dump(mode="json"),
        )
        self._record_observation(verifier, second_frame, second_classification.result)
        await self._transition(MissionState.CONSENSUS)
        fused = VerificationScoutAgent().fuse(
            self.classification.result if self.classification else second_classification.result,
            second_classification.result,
        )
        self.classification = CVClassification(
            raw_response={
                "primary": self.classification.raw_response if self.classification else None,
                "secondary": second_classification.raw_response,
            },
            result=fused,
            valid=second_classification.valid,
            validation_errors=second_classification.validation_errors,
        )
        self._validate_route_against_classification(fused)
        self.finding = self._build_finding(fused)
        self.event_store.emit(
            self.mission.mission_id,
            EventType.CONSENSUS_REACHED,
            state=self.mission.state,
            robot_id=verifier.id,
            sensor_id=second_frame.sensor_id,
            frame_path=second_frame.path,
            data={
                "classification": fused.model_dump(mode="json"),
                "finding": self.finding.model_dump(mode="json"),
            },
        )

    async def _error_safe(self, exc: Exception) -> MissionReport:
        await self._transition(MissionState.ERROR_SAFE)
        self.event_store.emit(
            self.mission.mission_id,
            EventType.ERROR,
            state=self.mission.state,
            robot_id=self.robot.id,
            data={"error": type(exc).__name__, "message": str(exc)},
        )
        try:
            await self.safety.run_checked(self.mission, "stop", self.robot.stop)
        except Exception as stop_exc:
            self.event_store.emit(
                self.mission.mission_id,
                EventType.ERROR,
                state=self.mission.state,
                robot_id=self.robot.id,
                data={"error": type(stop_exc).__name__, "message": str(stop_exc)},
            )
        return self._build_report(summary=f"Mission entered ERROR_SAFE: {exc}")

    def _build_report(self, summary: str | None = None) -> MissionReport:
        result = self.classification.result if self.classification else None
        safe_to_contact = result is not None and result.label == ClassificationLabel.NOT_MINE
        recommendation = result.recommended_action if result else RecommendedAction.HUMAN_REVIEW
        if result is not None and self.finding is None:
            self.finding = self._build_finding(result)
        if summary is None:
            summary = self._summary_for_result(result)
        return MissionReport(
            mission_id=self.mission.mission_id,
            state=self.mission.state,
            frame=self.frame,
            classification=result,
            recommendation=recommendation,
            safe_to_contact=safe_to_contact,
            summary=summary,
            observations=self.observations,
            finding=self.finding,
            route_trace=self.route_trace,
        )

    def _build_finding(self, result: ClassificationResult) -> Finding:
        return Finding(
            mission_id=self.mission.mission_id,
            label=result.label,
            confidence=result.confidence,
            safe_to_contact=result.label == ClassificationLabel.NOT_MINE,
            observations=[observation.observation_id for observation in self.observations],
            rationale=" ".join(result.evidence) or self._summary_for_result(result),
        )

    def _summary_for_result(self, result) -> str:
        if result is None:
            return "No classification was available; human review required."
        if result.label == ClassificationLabel.MINE:
            return "Mock target reported as MINE. No contact is allowed."
        if result.label == ClassificationLabel.NOT_MINE:
            return "Mock target reported as NOT_MINE. Digital marking only in P0."
        return "Mock target is UNCERTAIN. Request human review or second view."
