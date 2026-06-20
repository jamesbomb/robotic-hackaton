from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from safeground.event_store import JsonlEventStore
from safeground.models import EventType, Mission, SafeGroundConfig, SafetyDecision

T = TypeVar("T")


class SafetyGovernor:
    def __init__(self, config: SafeGroundConfig, event_store: JsonlEventStore) -> None:
        self.config = config
        self.event_store = event_store
        self.stop_requested = False

    def check(self, mission: Mission, action: str) -> SafetyDecision:
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
            robot_id=self.config.robot_id,
            data=decision.model_dump(mode="json"),
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

    def request_stop(self) -> None:
        self.stop_requested = True
