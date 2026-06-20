from __future__ import annotations

import re

from safeground.models import (
    AgentDecision,
    AgentDecisionType,
    SafeGroundConfig,
    UserIntent,
    UserIntentType,
)


STOP_TERMS = ("stop", "halt", "ferma", "fermati", "emergency", "blocca")
STATUS_TERMS = ("status", "stato", "report", "timeline")
START_TERMS = ("start", "avvia", "inizia", "ispeziona", "scansiona", "scan")


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
