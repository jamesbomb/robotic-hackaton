from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class RuntimeMode(StrEnum):
    MOCK = "mock"
    SIMULATION = "simulation"
    LIVE = "live"


class MissionState(StrEnum):
    IDLE = "IDLE"
    OBSERVE = "OBSERVE"
    CLASSIFY = "CLASSIFY"
    REPORT = "REPORT"
    MANUAL_STOP = "MANUAL_STOP"
    ERROR_SAFE = "ERROR_SAFE"
    UNCERTAIN = "UNCERTAIN"
    SECOND_OBSERVATION = "SECOND_OBSERVATION"
    CONSENSUS = "CONSENSUS"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class ClassificationLabel(StrEnum):
    MINE = "MINE"
    NOT_MINE = "NOT_MINE"
    UNCERTAIN = "UNCERTAIN"


class RecommendedAction(StrEnum):
    REPORT = "REPORT"
    SECOND_VIEW = "SECOND_VIEW"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class EventType(StrEnum):
    MISSION_STARTED = "MISSION_STARTED"
    ROBOT_STATUS_UPDATED = "ROBOT_STATUS_UPDATED"
    FRAME_CAPTURED = "FRAME_CAPTURED"
    CV_RESULT_RECEIVED = "CV_RESULT_RECEIVED"
    CV_RESULT_VALIDATED = "CV_RESULT_VALIDATED"
    STATE_CHANGED = "STATE_CHANGED"
    SAFETY_CHECK_PASSED = "SAFETY_CHECK_PASSED"
    SAFETY_CHECK_FAILED = "SAFETY_CHECK_FAILED"
    MISSION_REPORTED = "MISSION_REPORTED"
    MISSION_STOPPED = "MISSION_STOPPED"
    ERROR = "ERROR"


class SafeGroundConfig(BaseModel):
    runtime_mode: RuntimeMode = RuntimeMode.MOCK
    dry_run: bool = True
    robot_id: str = "mock-ugv"
    robot_role: str = "Primary Scout"
    sensor_id: str = "mock-camera"
    event_log_path: Path = Path("safeground_runs/events.jsonl")
    frame_fixture_dir: Path = Path(__file__).parent / "fixtures" / "frames"
    cv_fixture_dir: Path = Path(__file__).parent / "fixtures" / "cv"
    allowed_actions: set[str] = Field(
        default_factory=lambda: {"capture_frame", "stop", "hold_position"}
    )
    action_timeout_s: float = Field(default=2.0, gt=0.0)
    low_confidence_threshold: float = Field(default=0.4, ge=0.0, le=1.0)


class FrameRef(BaseModel):
    frame_id: str
    sensor_id: str
    source: Literal["fixture", "camera", "cyberwave"] = "fixture"
    path: Path
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    width: int | None = None
    height: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClassificationResult(BaseModel):
    label: ClassificationLabel
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: list[int] | None = None
    evidence: list[str] = Field(default_factory=list)
    recommended_action: RecommendedAction

    @field_validator("bbox")
    @classmethod
    def validate_bbox(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return value
        if len(value) != 4:
            raise ValueError("bbox must contain [x_min, y_min, x_max, y_max]")
        x_min, y_min, x_max, y_max = value
        if x_min >= x_max or y_min >= y_max:
            raise ValueError("bbox min coordinates must be less than max coordinates")
        return value


class CVClassification(BaseModel):
    raw_response: Any
    result: ClassificationResult
    valid: bool
    validation_errors: list[str] = Field(default_factory=list)


class SafetyDecision(BaseModel):
    action: str
    allowed: bool
    dry_run: bool
    reason: str
    timeout_s: float


class Mission(BaseModel):
    mission_id: str = Field(default_factory=lambda: f"mission-{uuid4().hex[:8]}")
    state: MissionState = MissionState.IDLE
    runtime_mode: RuntimeMode = RuntimeMode.MOCK
    dry_run: bool = True
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    stopped_at: datetime | None = None


class MissionReport(BaseModel):
    mission_id: str
    state: MissionState
    frame: FrameRef | None
    classification: ClassificationResult | None
    recommendation: RecommendedAction | None
    safe_to_contact: bool
    summary: str
