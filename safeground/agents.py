from __future__ import annotations

import re

from safeground.models import (
    AgentDecision,
    AgentDecisionType,
    BaseMovementAction,
    BaseMovementCommand,
    ClassificationLabel,
    ClassificationResult,
    MovementAgentPlan,
    MovementCommandRequest,
    RecommendedAction,
    RobotStatus,
    SafeGroundConfig,
    UserIntent,
    UserIntentType,
)


STOP_TERMS = ("stop", "halt", "ferma", "fermati", "emergency", "blocca")
STATUS_TERMS = ("status", "stato", "report", "timeline")
START_TERMS = ("start", "avvia", "inizia", "ispeziona", "scansiona", "scan")
FORWARD_TERMS = ("avanti", "forward", "prosegui", "procedi", "vai avanti", "move forward")
BACKWARD_TERMS = ("indietro", "back", "backward", "retrocedi", "vai indietro", "move backward")
LEFT_TERMS = ("sinistra", "left", "ruota a sinistra", "rotate left", "gira a sinistra")
RIGHT_TERMS = ("destra", "right", "ruota a destra", "rotate right", "gira a destra")


class CommandInterpreterAgent:
    """Rule-based stand-in for the chat/voice LLM command interpreter."""

    def parse(self, text: str) -> UserIntent:
        normalized = " ".join(text.lower().strip().split())
        target_sector = self._extract_sector(normalized)
        scenario_hint = self._extract_scenario(normalized)

        if not normalized:
            return UserIntent(
                intent=UserIntentType.UNKNOWN,
                original_text=text,
                reason="Empty command.",
            )

        if any(term in normalized for term in STOP_TERMS):
            return UserIntent(
                intent=UserIntentType.STOP_ALL,
                original_text=text,
                target_sector=target_sector,
                scenario_hint=scenario_hint,
                reason="Stop command detected; bypassing LLM planning.",
            )

        if any(term in normalized for term in STATUS_TERMS):
            return UserIntent(
                intent=UserIntentType.STATUS,
                original_text=text,
                target_sector=target_sector,
                scenario_hint=scenario_hint,
                reason="Status/report command detected.",
            )

        if any(term in normalized for term in START_TERMS):
            return UserIntent(
                intent=UserIntentType.START_MISSION,
                original_text=text,
                target_sector=target_sector,
                scenario_hint=scenario_hint,
                reason="Inspection command detected.",
            )

        return UserIntent(
            intent=UserIntentType.UNKNOWN,
            original_text=text,
            target_sector=target_sector,
            scenario_hint=scenario_hint,
            reason="Command is outside the P0 allow-list.",
        )

    def _extract_sector(self, text: str) -> str | None:
        match = re.search(r"\b([abc][1-3]|sector\s+[abc][1-3]|settore\s+[abc][1-3])\b", text)
        if not match:
            return None
        return match.group(1).split()[-1].upper()

    def _extract_scenario(self, text: str) -> str | None:
        if (
            "field" in text
            or "campo" in text
            or "lattine" in text
            or "lattina" in text
            or "test completo" in text
        ):
            return "FIELD"
        if "not_mine" in text or "non mine" in text or "innocuo" in text:
            return "NOT_MINE"
        if "uncertain" in text or "dubbio" in text or "incerto" in text:
            return "UNCERTAIN"
        if "mine" in text or "mina" in text:
            return "MINE"
        return None


class OrchestratorAgent:
    """Converts safe high-level intents into deterministic mission decisions."""

    def __init__(self, config: SafeGroundConfig) -> None:
        self.config = config

    def decide(self, intent: UserIntent) -> AgentDecision:
        if intent.intent == UserIntentType.STOP_ALL:
            return AgentDecision(
                decision=AgentDecisionType.STOP_ALL,
                action="stop",
                target_sector=intent.target_sector,
                assigned_robot=self.config.robot_id,
                scenario_hint=intent.scenario_hint,
                reason=intent.reason,
                constraints={"dry_run": self.config.dry_run},
            )

        if intent.intent == UserIntentType.STATUS:
            return AgentDecision(
                decision=AgentDecisionType.REPORT_STATUS,
                action="hold_position",
                target_sector=intent.target_sector,
                assigned_robot=self.config.robot_id,
                scenario_hint=intent.scenario_hint,
                reason=intent.reason,
                constraints={"dry_run": self.config.dry_run},
            )

        if intent.intent == UserIntentType.START_MISSION:
            return AgentDecision(
                decision=AgentDecisionType.RUN_MISSION,
                action="capture_frame",
                target_sector=intent.target_sector,
                assigned_robot=self.config.robot_id,
                scenario_hint=intent.scenario_hint,
                reason=intent.reason,
                constraints={
                    "dry_run": self.config.dry_run,
                    "no_contact": True,
                    "allowed_actions": sorted(self.config.allowed_actions),
                },
            )

        return AgentDecision(
            decision=AgentDecisionType.ASK_HUMAN,
            action="hold_position",
            target_sector=intent.target_sector,
            assigned_robot=self.config.robot_id,
            scenario_hint=intent.scenario_hint,
            requires_confirmation=True,
            reason=intent.reason,
            constraints={"dry_run": self.config.dry_run},
        )


class OperatorCommandAgent(CommandInterpreterAgent):
    """Named UI-facing command agent that reuses the safe P0 parser."""


class MovementCommandAgent:
    """Rule-based stand-in for the LLM movement planner.

    It only emits one bounded P0 base command, never continuous velocity.
    """

    def plan(self, request: MovementCommandRequest) -> MovementAgentPlan:
        normalized = " ".join(request.text.lower().strip().split())
        action = self._extract_action(normalized)
        if action is None:
            reason = (
                "Movement command rejected; use avanti/indietro/sinistra/destra. "
                "Stop is handled by the deterministic robot stop control."
            )
            return MovementAgentPlan(
                robot_id=request.robot_id,
                text=request.text,
                accepted=False,
                reason=reason,
                constraints=self._constraints(request),
            )

        command = BaseMovementCommand(
            action=action,
            movement_target=request.movement_target,
            operator_id=request.operator_id,
            operator_confirmed=request.operator_confirmed,
            distance_m=request.distance_m,
            angle_degrees=request.angle_degrees,
            reason=f"{request.reason} Planned from text: {request.text}",
        )
        return MovementAgentPlan(
            robot_id=request.robot_id,
            text=request.text,
            action=action,
            command=command,
            accepted=True,
            reason="Movement text mapped to a single bounded P0 base command.",
            constraints=self._constraints(request),
        )

    def _extract_action(self, text: str) -> BaseMovementAction | None:
        if any(term in text for term in STOP_TERMS):
            return None
        if any(term in text for term in FORWARD_TERMS):
            return BaseMovementAction.MOVE_FORWARD
        if any(term in text for term in BACKWARD_TERMS):
            return BaseMovementAction.MOVE_BACKWARD
        if any(term in text for term in LEFT_TERMS):
            return BaseMovementAction.ROTATE_LEFT
        if any(term in text for term in RIGHT_TERMS):
            return BaseMovementAction.ROTATE_RIGHT
        return None

    def _constraints(self, request: MovementCommandRequest) -> dict:
        return {
            "robot_id": request.robot_id,
            "movement_target": request.movement_target,
            "operator_confirmed": request.operator_confirmed,
            "max_distance_m": 0.5,
            "max_angle_degrees": 15.0,
            "continuous_velocity": False,
        }


class MissionOrchestratorAgent(OrchestratorAgent):
    def select_robot(self, robots: list[RobotStatus], role: str) -> str:
        for robot in robots:
            if robot.online and robot.role == role:
                return robot.robot_id
        return self.config.robot_id


class PrimaryScoutAgent:
    role = "Primary Scout"

    def assign(self, robots: list[RobotStatus]) -> str:
        for robot in robots:
            if robot.online and robot.role == self.role and "capture_frame" in robot.actions:
                return robot.robot_id
        for robot in robots:
            if robot.online and "capture_frame" in robot.actions:
                return robot.robot_id
        return "mock-ugv"


class VerificationScoutAgent:
    role = "Verification Scout"

    def assign(self, robots: list[RobotStatus], primary_robot_id: str) -> str | None:
        for robot in robots:
            if (
                robot.online
                and robot.robot_id != primary_robot_id
                and robot.role == self.role
                and "capture_frame" in robot.actions
            ):
                return robot.robot_id
        for robot in robots:
            if robot.online and robot.robot_id != primary_robot_id and "capture_frame" in robot.actions:
                return robot.robot_id
        return None

    def fuse(
        self,
        primary: ClassificationResult,
        secondary: ClassificationResult,
    ) -> ClassificationResult:
        if secondary.label != ClassificationLabel.UNCERTAIN and secondary.confidence >= 0.75:
            return ClassificationResult(
                label=secondary.label,
                confidence=secondary.confidence,
                bbox=secondary.bbox,
                evidence=[
                    *primary.evidence,
                    *secondary.evidence,
                    "Second observation resolved the uncertain primary view.",
                ],
                recommended_action=RecommendedAction.REPORT,
            )

        if primary.label == secondary.label and primary.label != ClassificationLabel.UNCERTAIN:
            return ClassificationResult(
                label=primary.label,
                confidence=min(primary.confidence, secondary.confidence),
                bbox=secondary.bbox or primary.bbox,
                evidence=[
                    *primary.evidence,
                    *secondary.evidence,
                    "Primary and verification observations agree.",
                ],
                recommended_action=RecommendedAction.REPORT,
            )

        return ClassificationResult(
            label=ClassificationLabel.UNCERTAIN,
            confidence=max(primary.confidence, secondary.confidence),
            bbox=secondary.bbox or primary.bbox,
            evidence=[
                *primary.evidence,
                *secondary.evidence,
                "Observations did not produce a safe consensus; human review required.",
            ],
            recommended_action=RecommendedAction.HUMAN_REVIEW,
        )


class MarkerAgent:
    role = "Marker Agent"

    def may_mark(self, classification: ClassificationResult) -> bool:
        return classification.label == ClassificationLabel.NOT_MINE
