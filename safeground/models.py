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
    MANUAL_TAKEOVER = "MANUAL_TAKEOVER"
    ERROR_SAFE = "ERROR_SAFE"
    UNCERTAIN = "UNCERTAIN"
    SECOND_OBSERVATION = "SECOND_OBSERVATION"
    CONSENSUS = "CONSENSUS"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class ClassificationLabel(StrEnum):
    MINE = "MINE"
    NOT_MINE = "NOT_MINE"
    UNCERTAIN = "UNCERTAIN"


class ManualArmAction(StrEnum):
    HOME = "home"
    HOLD_POSITION = "hold_position"
    NUDGE_JOINT = "nudge_joint"
    PLACE_SAFE_MARKER = "place_safe_marker"


class BaseMovementAction(StrEnum):
    MOVE_FORWARD = "move_forward"
    MOVE_BACKWARD = "move_backward"
    ROTATE_LEFT = "rotate_left"
    ROTATE_RIGHT = "rotate_right"


class RecommendedAction(StrEnum):
    REPORT = "REPORT"
    SECOND_VIEW = "SECOND_VIEW"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class RouteSafetyStatus(StrEnum):
    SAFE = "SAFE"
    UNSAFE = "UNSAFE"


class UserIntentType(StrEnum):
    START_MISSION = "START_MISSION"
    STOP_ALL = "STOP_ALL"
    STATUS = "STATUS"
    UNKNOWN = "UNKNOWN"


class AgentDecisionType(StrEnum):
    RUN_MISSION = "RUN_MISSION"
    STOP_ALL = "STOP_ALL"
    REPORT_STATUS = "REPORT_STATUS"
    ASK_HUMAN = "ASK_HUMAN"


class EventType(StrEnum):
    MISSION_STARTED = "MISSION_STARTED"
    USER_COMMAND_RECEIVED = "USER_COMMAND_RECEIVED"
    AGENT_INTENT_PARSED = "AGENT_INTENT_PARSED"
    AGENT_DECISION_MADE = "AGENT_DECISION_MADE"
    ROBOT_STATUS_UPDATED = "ROBOT_STATUS_UPDATED"
    FRAME_CAPTURED = "FRAME_CAPTURED"
    CV_RESULT_RECEIVED = "CV_RESULT_RECEIVED"
    CV_RESULT_VALIDATED = "CV_RESULT_VALIDATED"
    STATE_CHANGED = "STATE_CHANGED"
    SAFETY_CHECK_PASSED = "SAFETY_CHECK_PASSED"
    SAFETY_CHECK_FAILED = "SAFETY_CHECK_FAILED"
    MISSION_REPORTED = "MISSION_REPORTED"
    MISSION_STOPPED = "MISSION_STOPPED"
    MANUAL_ARM_COMMAND_REQUESTED = "MANUAL_ARM_COMMAND_REQUESTED"
    MANUAL_ARM_COMMAND_APPLIED = "MANUAL_ARM_COMMAND_APPLIED"
    BASE_MOVEMENT_COMMAND_REQUESTED = "BASE_MOVEMENT_COMMAND_REQUESTED"
    BASE_MOVEMENT_COMMAND_APPLIED = "BASE_MOVEMENT_COMMAND_APPLIED"
    ROUTE_RECORDED = "ROUTE_RECORDED"
    ROUTE_INVALIDATED = "ROUTE_INVALIDATED"
    ROUTE_REUSED_FOR_VERIFICATION = "ROUTE_REUSED_FOR_VERIFICATION"
    OBSERVATION_RECORDED = "OBSERVATION_RECORDED"
    CONSENSUS_REACHED = "CONSENSUS_REACHED"
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
        default_factory=lambda: {
            "capture_frame",
            "stop",
            "hold_position",
            "move_forward",
            "move_backward",
            "rotate_left",
            "rotate_right",
            "manual_arm_home",
            "manual_arm_hold_position",
            "manual_arm_nudge_joint",
            "manual_arm_place_safe_marker",
        }
    )
    action_timeout_s: float = Field(default=2.0, gt=0.0)
    max_base_move_distance_m: float = Field(default=0.5, gt=0.0)
    max_base_rotate_degrees: float = Field(default=15.0, gt=0.0)
    manual_arm_step_limit_degrees: float = Field(default=5.0, gt=0.0)
    so101_allowed_joints: set[str] = Field(
        default_factory=lambda: {
            "base",
            "shoulder",
            "elbow",
            "wrist_pitch",
            "wrist_roll",
            "gripper",
        }
    )
    low_confidence_threshold: float = Field(default=0.4, ge=0.0, le=1.0)
    verification_scenario: str = "MINE"
    route_over_mine: bool = False


class RobotPose(BaseModel):
    x: float = 0.0
    y: float = 0.0
    yaw: float = 0.0


class RobotStatus(BaseModel):
    robot_id: str
    role: str
    online: bool = True
    mode: RuntimeMode = RuntimeMode.MOCK
    task: str = "idle"
    battery_percent: int | None = None
    sensors: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    heartbeat_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    pose: RobotPose = Field(default_factory=RobotPose)
    note: str | None = None


class RobotCapabilityMap(BaseModel):
    robots: list[RobotStatus] = Field(default_factory=list)


class CommandRequest(BaseModel):
    text: str | None = None
    scenario: str = "FIELD"
    target_sector: str | None = None


class ManualArmCommand(BaseModel):
    action: ManualArmAction
    operator_id: str = "operator"
    operator_confirmed: bool = False
    joint_name: str | None = None
    delta_degrees: float = 0.0
    target_label: ClassificationLabel | None = None
    reason: str = "Manual SO-101 human takeover."

    @field_validator("delta_degrees")
    @classmethod
    def validate_delta(cls, value: float) -> float:
        if abs(value) > 5.0:
            raise ValueError("manual joint nudge must stay within +/-5 degrees")
        return value


class ManualArmResult(BaseModel):
    command_id: str = Field(default_factory=lambda: f"arm-command-{uuid4().hex[:8]}")
    robot_id: str
    action: ManualArmAction
    applied: bool
    dry_run: bool
    joint_name: str | None = None
    joint_positions_degrees: dict[str, float] = Field(default_factory=dict)
    executed_sequence: list[str] = Field(default_factory=list)
    reason: str


class BaseMovementCommand(BaseModel):
    action: BaseMovementAction
    operator_id: str = "operator"
    operator_confirmed: bool = False
    distance_m: float = 0.25
    angle_degrees: float = 10.0
    reason: str = "P0 bounded base movement."

    @field_validator("distance_m")
    @classmethod
    def validate_distance(cls, value: float) -> float:
        if value <= 0 or value > 0.5:
            raise ValueError("base movement distance must be > 0 and <= 0.5 m")
        return value

    @field_validator("angle_degrees")
    @classmethod
    def validate_angle(cls, value: float) -> float:
        if value <= 0 or value > 15.0:
            raise ValueError("base rotation angle must be > 0 and <= 15 degrees")
        return value


class BaseMovementResult(BaseModel):
    command_id: str = Field(default_factory=lambda: f"base-move-{uuid4().hex[:8]}")
    robot_id: str
    action: BaseMovementAction
    applied: bool
    dry_run: bool
    pose: RobotPose
    executed_sequence: list[str] = Field(default_factory=list)
    reason: str


class Observation(BaseModel):
    observation_id: str = Field(default_factory=lambda: f"obs-{uuid4().hex[:8]}")
    mission_id: str
    robot_id: str
    sensor_id: str
    sector: str | None = None
    pose: RobotPose = Field(default_factory=RobotPose)
    frame: FrameRef
    classification: ClassificationResult
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Finding(BaseModel):
    finding_id: str = Field(default_factory=lambda: f"finding-{uuid4().hex[:8]}")
    mission_id: str
    sector: str | None = None
    label: ClassificationLabel
    confidence: float = Field(ge=0.0, le=1.0)
    safe_to_contact: bool
    observations: list[str] = Field(default_factory=list)
    rationale: str
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RoutePoint(BaseModel):
    sector: str | None = None
    pose: RobotPose = Field(default_factory=RobotPose)
    note: str = "route point"
    over_hazard: bool = False


class RouteTrace(BaseModel):
    route_id: str = Field(default_factory=lambda: f"route-{uuid4().hex[:8]}")
    mission_id: str
    robot_id: str
    points: list[RoutePoint] = Field(default_factory=list)
    status: RouteSafetyStatus = RouteSafetyStatus.SAFE
    reusable_by: list[str] = Field(default_factory=list)
    invalidation_reason: str | None = None


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


class UserIntent(BaseModel):
    intent: UserIntentType
    original_text: str
    target_sector: str | None = None
    requested_robot: str = "auto"
    scenario_hint: str | None = None
    requires_confirmation: bool = False
    reason: str


class AgentDecision(BaseModel):
    decision: AgentDecisionType
    action: str
    target_sector: str | None = None
    assigned_robot: str = "auto"
    scenario_hint: str | None = None
    requires_confirmation: bool = False
    reason: str
    constraints: dict[str, Any] = Field(default_factory=dict)


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
    observations: list[Observation] = Field(default_factory=list)
    finding: Finding | None = None
    route_trace: RouteTrace | None = None


class MissionSnapshot(BaseModel):
    mission: Mission | None = None
    report: MissionReport | None = None
    robots: list[RobotStatus] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)
