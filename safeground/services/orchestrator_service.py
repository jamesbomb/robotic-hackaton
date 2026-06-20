from __future__ import annotations

from safeground.adapters import RobotAdapter, build_mock_fleet
from safeground.agents import OperatorCommandAgent, OrchestratorAgent
from safeground.cv import MockCVClient
from safeground.event_store import Event, JsonlEventStore
from safeground.mission import MissionRunner
from safeground.models import (
    AgentDecisionType,
    CommandRequest,
    EventType,
    ManualArmCommand,
    ManualArmResult,
    MissionReport,
    MissionSnapshot,
    MissionState,
    RobotStatus,
    SafeGroundConfig,
)
from safeground.safety import SafetyGovernor


class OrchestratorService:
    def __init__(self, config: SafeGroundConfig | None = None) -> None:
        self.config = config or SafeGroundConfig()
        self.event_store = JsonlEventStore(self.config.event_log_path)
        self.fleet = build_mock_fleet(self.config)
        self.latest_report: MissionReport | None = None
        self.active_runner: MissionRunner | None = None

    async def robot_statuses(self) -> list[RobotStatus]:
        return [await robot.status() for robot in self.fleet.values()]

    async def start_mission(self, scenario: str = "MINE") -> MissionReport:
        runner = self._build_runner()
        self.active_runner = runner
        report = await runner.run(scenario)
        self.latest_report = report
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
            report=self.latest_report,
            robots=await self.robot_statuses(),
            events=[event.model_dump(mode="json") for event in self.events(limit=100)],
        )

    def _build_runner(self) -> MissionRunner:
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
