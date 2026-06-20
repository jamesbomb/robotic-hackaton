from __future__ import annotations

from pydantic import BaseModel

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from safeground.models import CommandRequest
from safeground.services.orchestrator_service import OrchestratorService


class MissionStartRequest(BaseModel):
    scenario: str = "MINE"


service = OrchestratorService()
app = FastAPI(title="SafeGround Ops Console", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict:
    return {
        "ok": True,
        "runtime_mode": service.config.runtime_mode,
        "dry_run": service.config.dry_run,
    }


@app.get("/api/snapshot")
async def snapshot():
    return await service.snapshot()


@app.post("/api/missions")
async def create_mission(request: MissionStartRequest):
    return await service.start_mission(request.scenario)


@app.post("/api/missions/start")
async def start_mission(request: MissionStartRequest):
    return await service.start_mission(request.scenario)


@app.post("/api/missions/stop")
async def stop_mission():
    return await service.stop_all()


@app.post("/api/commands")
async def run_command(request: CommandRequest):
    return await service.run_command(request)


@app.get("/api/robots")
async def robots():
    return await service.robot_statuses()


@app.get("/api/robots/{robot_id}/capabilities")
async def robot_capabilities(robot_id: str):
    robot = service.fleet[robot_id]
    return await robot.capabilities()


@app.post("/api/robots/{robot_id}/stop")
async def stop_robot(robot_id: str):
    await service.fleet[robot_id].stop()
    return await service.robot_statuses()


@app.post("/api/robots/{robot_id}/capture")
async def capture_robot_frame(robot_id: str):
    robot = service.fleet[robot_id]
    return await robot.capture_frame(robot.sensor_id)


@app.get("/api/events")
async def events(limit: int = 200):
    return service.events(limit=limit)


@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket) -> None:
    await websocket.accept()
    queue = service.event_store.subscribe()
    try:
        for event in service.events(limit=100):
            await websocket.send_json(event.model_dump(mode="json"))
        while True:
            event = await queue.get()
            await websocket.send_json(event.model_dump(mode="json"))
    except WebSocketDisconnect:
        service.event_store.unsubscribe(queue)
