from __future__ import annotations

from contextlib import asynccontextmanager

from pydantic import BaseModel

from fastapi import FastAPI, HTTPException, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from safeground.models import (
    BaseMovementCommand,
    CommandRequest,
    ImageClassifyRequest,
    ManualArmCommand,
    MovementCommandRequest,
    ObjectMarkRequest,
    ObjectPickupFinishRequest,
    ObjectPickupReplayRequest,
    ObjectPickupStartRequest,
    RobotActivationRequest,
    RuntimeConfigRequest,
    ScoutRouteCommand,
)
from safeground.services.cyberwave_movement_feed import CyberwaveMovementFeedMonitor
from safeground.services.orchestrator_service import OrchestratorService


class MissionStartRequest(BaseModel):
    scenario: str = "FIELD"


service = OrchestratorService()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    service.start_cyberwave_movement_feed()
    service.start_live_vision()
    try:
        yield
    finally:
        service.stop_live_vision()
        service.stop_cyberwave_movement_feed()


app = FastAPI(title="SafeGround Ops Console", version="0.1.0", lifespan=lifespan)

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


@app.get("/api/runtime")
async def runtime():
    return service.runtime_status()


@app.post("/api/runtime")
async def update_runtime(request: RuntimeConfigRequest):
    try:
        return await service.update_runtime(request)
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/snapshot")
async def snapshot():
    return await service.snapshot()


@app.get("/api/risk-map")
async def risk_map():
    return service.risk_map_state()


@app.post("/api/risk-map/clear")
async def clear_risk_map():
    return service.clear_risk_map()


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


@app.post("/api/observations/mark")
async def mark_latest_object(request: ObjectMarkRequest):
    try:
        return await service.mark_latest_object(request)
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/robots")
async def robots():
    return await service.robot_statuses()


@app.get("/api/camera-streams")
async def camera_streams():
    return service.camera_streams()


@app.get("/api/cyberwave/robots")
async def cyberwave_robots():
    return service.discover_cyberwave_robots()


@app.get("/api/object-pickup/sessions")
async def object_pickup_sessions():
    return service.object_pickup_sessions


@app.post("/api/object-pickup/start")
async def start_object_pickup(request: ObjectPickupStartRequest):
    try:
        return await service.start_object_pickup(request)
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/object-pickup/finish")
async def finish_object_pickup(request: ObjectPickupFinishRequest):
    try:
        return await service.finish_object_pickup(request)
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/object-pickup/replay")
async def replay_object_pickup(request: ObjectPickupReplayRequest):
    try:
        return await service.replay_object_pickup(request)
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/robots/{robot_id}/capabilities")
async def robot_capabilities(robot_id: str):
    robot = service.fleet[robot_id]
    return await robot.capabilities()


@app.post("/api/robots/{robot_id}/stop")
async def stop_robot(robot_id: str):
    try:
        return await service.stop_robot(robot_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Robot not found") from exc


@app.post("/api/robots/{robot_id}/activate")
async def activate_robot(robot_id: str, request: RobotActivationRequest):
    try:
        return await service.activate_robot(robot_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Robot not found") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/robots/{robot_id}/manual-arm")
async def manual_arm_takeover(robot_id: str, request: ManualArmCommand):
    if robot_id not in service.fleet:
        raise HTTPException(status_code=404, detail="Robot not found")
    try:
        return await service.manual_arm_takeover(robot_id, request)
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/robots/{robot_id}/move")
async def move_robot_base(robot_id: str, request: BaseMovementCommand):
    if robot_id not in service.fleet:
        raise HTTPException(status_code=404, detail="Robot not found")
    try:
        return await service.move_robot_base(robot_id, request)
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/robots/go2/movement-command")
async def run_go2_movement_command(request: MovementCommandRequest):
    try:
        return await service.run_movement_command(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Robot not found") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/robots/go2/route-plan")
async def plan_go2_route(request: ScoutRouteCommand):
    try:
        return await service.plan_scout_route(request)
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/robots/{robot_id}/capture")
async def capture_robot_frame(robot_id: str):
    robot = service.fleet[robot_id]
    return await robot.capture_frame(robot.sensor_id)


@app.get("/api/robots/{robot_id}/latest-frame")
async def latest_robot_frame(robot_id: str):
    try:
        frame_bytes, media_type = await service.latest_robot_frame(robot_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Robot not found") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Response(
        content=frame_bytes,
        media_type=media_type,
        headers={"Cache-Control": "no-store"},
    )


@app.post("/api/robots/{robot_id}/classify-frame")
async def classify_robot_frame(robot_id: str):
    try:
        return await service.classify_robot_frame(robot_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Robot not found") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/vision/classify-image")
async def classify_image(request: ImageClassifyRequest):
    try:
        return await service.classify_image(request)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/vision/status")
async def vision_status():
    return {
        "status": service.live_vision_status(),
        "latest": service.latest_live_vision_result(),
    }


@app.get("/api/vision/live-frame")
async def vision_live_frame():
    frame_bytes = service.latest_live_vision_frame()
    if not frame_bytes:
        raise HTTPException(status_code=503, detail="Live vision frame not available yet.")
    return Response(
        content=frame_bytes,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store"},
    )


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
