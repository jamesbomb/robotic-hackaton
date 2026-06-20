from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from safeground.event_store import JsonlEventStore
from safeground.models import (
    BaseMovementAction,
    BaseMovementCommand,
    ClassificationLabel,
    EventType,
    ManualArmAction,
    ManualArmCommand,
    Mission,
    SafeGroundConfig,
    SafetyDecision,
)

T = TypeVar("T")


class SafetyGovernor:
    def __init__(self, config: SafeGroundConfig, event_store: JsonlEventStore) -> None:
        self.config = config
        self.event_store = event_store
        self.stop_requested = False

    def check(
        self,
        mission: Mission,
        action: str,
        *,
        robot_id: str | None = None,
        context: dict | None = None,
    ) -> SafetyDecision:
        allowed = action in self.config.allowed_actions
        reason = "allowed by P0 safety allow-list" if allowed else "blocked by safety allow-list"
        decision = SafetyDecision(
            action=action,
            allowed=allowed,
            dry_run=self.config.dry_run,
            reason=reason,
            timeout_s=self.config.action_timeout_s,
        )
        self.event_store.emit(
            mission.mission_id,
            EventType.SAFETY_CHECK_PASSED if allowed else EventType.SAFETY_CHECK_FAILED,
            state=mission.state,
            robot_id=robot_id or self.config.robot_id,
            data={
                **decision.model_dump(mode="json"),
                "context": context or {},
            },
        )
        return decision

    def check_manual_arm_command(
        self,
        mission: Mission,
        robot_id: str,
        command: ManualArmCommand,
    ) -> SafetyDecision:
        action = f"manual_arm_{command.action}"
        reasons: list[str] = []

        if action not in self.config.allowed_actions:
            reasons.append("blocked by safety allow-list")
        if robot_id.lower() not in {"so101", "so-101"}:
            reasons.append("manual arm takeover is restricted to SO-101")
        if not command.operator_confirmed:
            reasons.append("operator confirmation is required")
        if command.action == ManualArmAction.NUDGE_JOINT:
            if command.joint_name not in self.config.so101_allowed_joints:
                reasons.append("joint is not in the SO-101 allow-list")
            if abs(command.delta_degrees) > self.config.manual_arm_step_limit_degrees:
                reasons.append("joint nudge exceeds configured step limit")
            if command.delta_degrees == 0:
                reasons.append("joint nudge must be non-zero")
        if (
            command.action == ManualArmAction.PLACE_SAFE_MARKER
            and command.target_label != ClassificationLabel.NOT_MINE
        ):
            reasons.append("safe marker preset requires a NOT_MINE target")

        allowed = not reasons
        decision = SafetyDecision(
            action=action,
            allowed=allowed,
            dry_run=self.config.dry_run,
            reason="; ".join(reasons) if reasons else "manual SO-101 command allowed",
            timeout_s=self.config.action_timeout_s,
        )
        self.event_store.emit(
            mission.mission_id,
            EventType.SAFETY_CHECK_PASSED if allowed else EventType.SAFETY_CHECK_FAILED,
            state=mission.state,
            robot_id=robot_id,
            data={
                **decision.model_dump(mode="json"),
                "command": command.model_dump(mode="json"),
            },
        )
        return decision

    def check_base_movement_command(
        self,
        mission: Mission,
        robot_id: str,
        command: BaseMovementCommand,
    ) -> SafetyDecision:
        reasons: list[str] = []

        if command.action.value not in self.config.allowed_actions:
            reasons.append("blocked by safety allow-list")
        if robot_id.lower() in {"so101", "so-101", "fixed-camera"}:
            reasons.append("base movement is restricted to mobile robots")
        if not command.operator_confirmed:
            reasons.append("operator confirmation is required")
        if command.action in {
            BaseMovementAction.MOVE_FORWARD,
            BaseMovementAction.MOVE_BACKWARD,
        } and command.distance_m > self.config.max_base_move_distance_m:
            reasons.append("base movement distance exceeds configured P0 limit")
        if command.action in {
            BaseMovementAction.ROTATE_LEFT,
            BaseMovementAction.ROTATE_RIGHT,
        } and command.angle_degrees > self.config.max_base_rotate_degrees:
            reasons.append("base rotation exceeds configured P0 limit")

        allowed = not reasons
        decision = SafetyDecision(
            action=command.action.value,
            allowed=allowed,
            dry_run=self.config.dry_run,
            reason="; ".join(reasons) if reasons else "bounded P0 base movement allowed",
            timeout_s=self.config.action_timeout_s,
        )
        self.event_store.emit(
            mission.mission_id,
            EventType.SAFETY_CHECK_PASSED if allowed else EventType.SAFETY_CHECK_FAILED,
            state=mission.state,
            robot_id=robot_id,
            data={
                **decision.model_dump(mode="json"),
                "command": command.model_dump(mode="json"),
            },
        )
        return decision

    async def run_checked(
        self,
        mission: Mission,
        action: str,
        operation: Callable[[], Awaitable[T]],
    ) -> T:
        decision = self.check(mission, action)
        if not decision.allowed:
            raise PermissionError(decision.reason)
        return await asyncio.wait_for(operation(), timeout=decision.timeout_s)

    async def run_manual_arm_checked(
        self,
        mission: Mission,
        robot_id: str,
        command: ManualArmCommand,
        operation: Callable[[], Awaitable[T]],
    ) -> T:
        decision = self.check_manual_arm_command(mission, robot_id, command)
        if not decision.allowed:
            raise PermissionError(decision.reason)
        return await asyncio.wait_for(operation(), timeout=decision.timeout_s)

    async def run_base_movement_checked(
        self,
        mission: Mission,
        robot_id: str,
        command: BaseMovementCommand,
        operation: Callable[[], Awaitable[T]],
    ) -> T:
        decision = self.check_base_movement_command(mission, robot_id, command)
        if not decision.allowed:
            raise PermissionError(decision.reason)
        return await asyncio.wait_for(operation(), timeout=decision.timeout_s)

    def request_stop(self) -> None:
        self.stop_requested = True
