from __future__ import annotations

from datetime import UTC, datetime

from safeground.adapters import MockRobotAdapter
from safeground.cv import MockCVClient
from safeground.event_store import JsonlEventStore
from safeground.models import (
    CVClassification,
    ClassificationLabel,
    EventType,
    FrameRef,
    Mission,
    MissionReport,
    MissionState,
    RecommendedAction,
    SafeGroundConfig,
)
from safeground.safety import SafetyGovernor


class MissionRunner:
    def __init__(
        self,
        config: SafeGroundConfig,
        robot: MockRobotAdapter,
        cv_client: MockCVClient,
        event_store: JsonlEventStore,
        safety: SafetyGovernor,
    ) -> None:
        self.config = config
        self.robot = robot
        self.cv_client = cv_client
        self.event_store = event_store
        self.safety = safety
        self.mission = Mission(runtime_mode=config.runtime_mode, dry_run=config.dry_run)
        self.frame: FrameRef | None = None
        self.classification: CVClassification | None = None

    async def run(self, scenario: str) -> MissionReport:
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
            },
        )

        try:
            await self._record_robot_status()
            await self._transition(MissionState.OBSERVE)
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

            if self.safety.stop_requested:
                return await self.stop()

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
        health = await self.robot.health()
        capabilities = await self.robot.capabilities()
        self.event_store.emit(
            self.mission.mission_id,
            EventType.ROBOT_STATUS_UPDATED,
            state=self.mission.state,
            robot_id=self.robot.id,
            sensor_id=self.config.sensor_id,
            data={"health": health, "capabilities": capabilities},
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
        )

    def _summary_for_result(self, result) -> str:
        if result is None:
            return "No classification was available; human review required."
        if result.label == ClassificationLabel.MINE:
            return "Mock target reported as MINE. No contact is allowed."
        if result.label == ClassificationLabel.NOT_MINE:
            return "Mock target reported as NOT_MINE. Digital marking only in P0."
        return "Mock target is UNCERTAIN. Request human review or second view."
