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
    STRAFE_LEFT = "strafe_left"
    STRAFE_RIGHT = "strafe_right"
    ROTATE_LEFT = "rotate_left"
    ROTATE_RIGHT = "rotate_right"


class MovementTarget(StrEnum):
    AUTO = "auto"
    VIRTUAL = "virtual"
    PHYSICAL = "physical"
    BOTH = "both"


class CameraSource(StrEnum):
    PC = "pc"
    ROBOT = "robot"


class RobotActivationMode(StrEnum):
    READY = "ready"
    ARMED = "armed"


class MovementFSMState(StrEnum):
    IDLE = "IDLE"
    PLANNING = "PLANNING"
    PLANNED = "PLANNED"
    SAFETY_CHECKED = "SAFETY_CHECKED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    STOPPED = "STOPPED"
    REJECTED = "REJECTED"


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
    RUNTIME_CONFIG_UPDATED = "RUNTIME_CONFIG_UPDATED"
    CYBERWAVE_ROBOTS_DISCOVERED = "CYBERWAVE_ROBOTS_DISCOVERED"
    ROBOT_ACTIVATION_UPDATED = "ROBOT_ACTIVATION_UPDATED"
    MOVEMENT_COMMAND_RECEIVED = "MOVEMENT_COMMAND_RECEIVED"
    MOVEMENT_AGENT_DECISION_MADE = "MOVEMENT_AGENT_DECISION_MADE"
    MOVEMENT_STATE_CHANGED = "MOVEMENT_STATE_CHANGED"
    ROBOT_STOP_REQUESTED = "ROBOT_STOP_REQUESTED"
    ROBOT_STOPPED = "ROBOT_STOPPED"
    MANUAL_ARM_COMMAND_REQUESTED = "MANUAL_ARM_COMMAND_REQUESTED"
    MANUAL_ARM_COMMAND_APPLIED = "MANUAL_ARM_COMMAND_APPLIED"
    BASE_MOVEMENT_COMMAND_REQUESTED = "BASE_MOVEMENT_COMMAND_REQUESTED"
    BASE_MOVEMENT_COMMAND_APPLIED = "BASE_MOVEMENT_COMMAND_APPLIED"
    OBJECT_PICKUP_SESSION_STARTED = "OBJECT_PICKUP_SESSION_STARTED"
    OBJECT_PICKUP_STEP_RECORDED = "OBJECT_PICKUP_STEP_RECORDED"
    OBJECT_PICKUP_SESSION_FINISHED = "OBJECT_PICKUP_SESSION_FINISHED"
    OBJECT_PICKUP_TEMPLATE_REPLAYED = "OBJECT_PICKUP_TEMPLATE_REPLAYED"
    SCOUT_ROUTE_PLANNED = "SCOUT_ROUTE_PLANNED"
    POINT_MAP_UPDATED = "POINT_MAP_UPDATED"
    ROUTE_RECORDED = "ROUTE_RECORDED"
    ROUTE_INVALIDATED = "ROUTE_INVALIDATED"
    ROUTE_REUSED_FOR_VERIFICATION = "ROUTE_REUSED_FOR_VERIFICATION"
    OBSERVATION_RECORDED = "OBSERVATION_RECORDED"
    OBJECT_MARKED = "OBJECT_MARKED"
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
    cyberwave_config_dir: Path = Field(default_factory=lambda: Path.home() / ".cyberwave")
    allowed_actions: set[str] = Field(
        default_factory=lambda: {
            "capture_frame",
            "stop",
            "hold_position",
            "move_forward",
            "move_backward",
            "strafe_left",
            "strafe_right",
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
    mqtt_host: str = "localhost"
    mqtt_port: int = Field(default=1883, gt=0, le=65535)
    mqtt_topic_prefix: str = "safeground/robots"
    mqtt_qos: int = Field(default=1, ge=0, le=2)
    mqtt_timeout_s: float = Field(default=2.0, gt=0.0)
    cyberwave_virtual_sync: bool = True
    robot_movement_target: MovementTarget = MovementTarget.VIRTUAL
    camera_source: CameraSource = CameraSource.PC


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


class RuntimeConfigRequest(BaseModel):
    runtime_mode: RuntimeMode = RuntimeMode.MOCK
    dry_run: bool = True
    robot_movement_target: MovementTarget | None = None
    camera_source: CameraSource | None = None
    operator_id: str = "operator"
    operator_confirmed: bool = False
    reason: str = "Operator runtime mode change."


class RuntimeStatus(BaseModel):
    runtime_mode: RuntimeMode
    dry_run: bool
    robot_movement_target: MovementTarget = MovementTarget.VIRTUAL
    camera_source: CameraSource = CameraSource.PC
    live_adapter_ready: bool = False
    note: str = "Mock adapters are active; no hardware commands are sent."


class CyberwaveRobot(BaseModel):
    twin_uuid: str
    name: str
    robot_id: str
    registry_id: str | None = None
    slug: str | None = None
    has_stream: bool = False
    stream_url: str | None = None
    browser_url: str | None = None
    available_actions: list[str] = Field(default_factory=list)
    source: str = "local"
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RobotActivationRequest(BaseModel):
    operator_id: str = "operator"
    operator_confirmed: bool = False
    activation_mode: RobotActivationMode = RobotActivationMode.READY
    allow_physical: bool = False
    reason: str = "Operator activated robot from SafeGround dashboard."


class RobotActivationState(BaseModel):
    robot_id: str
    available: bool = False
    ready: bool = False
    armed: bool = False
    activation_mode: RobotActivationMode | None = None
    physical_enabled: bool = False
    virtual_enabled: bool = True
    operator_id: str | None = None
    reason: str | None = None
    last_check: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ObjectMarkRequest(BaseModel):
    label: ClassificationLabel
    operator_id: str = "operator"
    reason: str = "Operator marked object from camera panel."


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
    movement_target: MovementTarget = MovementTarget.AUTO
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
    movement_target: MovementTarget = MovementTarget.AUTO
    virtual_applied: bool = False
    physical_applied: bool = False
    executed_sequence: list[str] = Field(default_factory=list)
    reason: str


class MovementCommandRequest(BaseModel):
    text: str
    robot_id: str = "go2"
    movement_target: MovementTarget = MovementTarget.VIRTUAL
    operator_id: str = "operator"
    operator_confirmed: bool = False
    distance_m: float = 0.25
    angle_degrees: float = 10.0
    reason: str = "Operator requested LLM-assisted bounded movement."

    @field_validator("distance_m")
    @classmethod
    def validate_distance(cls, value: float) -> float:
        if value <= 0 or value > 0.5:
            raise ValueError("movement command distance must be > 0 and <= 0.5 m")
        return value

    @field_validator("angle_degrees")
    @classmethod
    def validate_angle(cls, value: float) -> float:
        if value <= 0 or value > 15.0:
            raise ValueError("movement command rotation must be > 0 and <= 15 degrees")
        return value


class MovementAgentPlan(BaseModel):
    plan_id: str = Field(default_factory=lambda: f"movement-plan-{uuid4().hex[:8]}")
    robot_id: str = "go2"
    text: str
    action: BaseMovementAction | None = None
    command: BaseMovementCommand | None = None
    accepted: bool
    reason: str
    constraints: dict[str, Any] = Field(default_factory=dict)


class MovementCommandResult(BaseModel):
    state: MovementFSMState
    plan: MovementAgentPlan
    result: BaseMovementResult | None = None
    reason: str


class MovementControllerState(BaseModel):
    state: MovementFSMState = MovementFSMState.IDLE
    robot_id: str = "go2"
    last_plan: MovementAgentPlan | None = None
    last_result: BaseMovementResult | None = None
    reason: str = "Movement controller idle."
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class MapPoint(BaseModel):
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)


class MapObstacle(BaseModel):
    obstacle_id: str = Field(default_factory=lambda: f"obstacle-{uuid4().hex[:8]}")
    label: str
    position: MapPoint
    radius: float = Field(default=0.05, gt=0.0, le=0.25)
    source: str = "mock"


class ScoutRouteCommand(BaseModel):
    robot_id: str = "go2"
    operator_id: str = "operator"
    operator_confirmed: bool = False
    waypoints: list[MapPoint] = Field(min_length=2, max_length=12)
    reason: str = "Operator-drawn scout route."


class ScoutRouteResult(BaseModel):
    route_id: str = Field(default_factory=lambda: f"scout-route-{uuid4().hex[:8]}")
    robot_id: str
    accepted: bool
    dry_run: bool
    waypoints: list[MapPoint]
    point_map: list[MapPoint]
    obstacles: list[MapObstacle] = Field(default_factory=list)
    reason: str


class CameraStream(BaseModel):
    twin_id: str
    robot_id: str
    source_url: str
    browser_url: str
    status: str = "configured"


class ObjectPickupStartRequest(BaseModel):
    operator_id: str = "operator"
    operator_confirmed: bool = False
    object_label: str = "manual_pickup_object"
    reason: str = "Operator starts assisted object pickup recording."


class ObjectPickupFinishRequest(BaseModel):
    session_id: str | None = None
    operator_id: str = "operator"
    save_as_template: bool = True
    reason: str = "Operator saved assisted object pickup recording."


class ObjectPickupReplayRequest(BaseModel):
    session_id: str
    operator_id: str = "operator"
    operator_confirmed: bool = False
    reason: str = "Operator selected a recorded pickup template."


class ObjectPickupStep(BaseModel):
    step_id: str = Field(default_factory=lambda: f"pickup-step-{uuid4().hex[:8]}")
    step_type: str
    robot_id: str
    action: str
    data: dict[str, Any] = Field(default_factory=dict)
    camera_streams: list[CameraStream] = Field(default_factory=list)
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ObjectPickupSession(BaseModel):
    session_id: str = Field(default_factory=lambda: f"pickup-{uuid4().hex[:8]}")
    object_label: str
    operator_id: str
    status: Literal["recording", "saved", "replayed"] = "recording"
    go2_posture_action: str = "stand_down"
    camera_streams: list[CameraStream] = Field(default_factory=list)
    steps: list[ObjectPickupStep] = Field(default_factory=list)
    reason: str
    replay_count: int = 0
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None


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
    runtime: RuntimeStatus
    report: MissionReport | None = None
    robots: list[RobotStatus] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)
    camera_streams: list[CameraStream] = Field(default_factory=list)
    cyberwave_robots: list[CyberwaveRobot] = Field(default_factory=list)
    robot_activations: list[RobotActivationState] = Field(default_factory=list)
    movement_controller: MovementControllerState = Field(default_factory=MovementControllerState)
    scout_route: ScoutRouteResult | None = None
    object_pickup_sessions: list[ObjectPickupSession] = Field(default_factory=list)
    active_object_pickup_session: ObjectPickupSession | None = None
