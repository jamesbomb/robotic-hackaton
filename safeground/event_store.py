from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from safeground.models import EventType, MissionState


class Event(BaseModel):
    mission_id: str
    event_type: EventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    state: MissionState | None = None
    robot_id: str | None = None
    sensor_id: str | None = None
    frame_path: Path | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class JsonlEventStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.events: list[Event] = []
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: Event) -> Event:
        self.events.append(event)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.model_dump(mode="json"), ensure_ascii=True) + "\n")
        return event

    def emit(
        self,
        mission_id: str,
        event_type: EventType,
        *,
        state: MissionState | None = None,
        robot_id: str | None = None,
        sensor_id: str | None = None,
        frame_path: Path | None = None,
        data: dict[str, Any] | None = None,
    ) -> Event:
        return self.append(
            Event(
                mission_id=mission_id,
                event_type=event_type,
                state=state,
                robot_id=robot_id,
                sensor_id=sensor_id,
                frame_path=frame_path,
                data=data or {},
            )
        )
