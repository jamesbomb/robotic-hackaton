# SafeGround P0 Development Plan

## Goal

Build the smallest repeatable SafeGround demo that proves the loop:

```text
Frame capture -> External CV classification -> Mission decision -> Dashboard report -> Safety stop
```

P0 optimizes for a working prototype, fast iteration, and demo reliability. It does not include training, detector development, mine detection claims, autonomous navigation, SO101 marker handling, or production hardening.

## Non-Negotiable Scope

- Operate only with inert mock objects in a controlled demo area.
- Treat computer vision as an external dependency owned by another teammate.
- Integrate CV only through a JSON/Pydantic contract, fixtures, and a mock classifier.
- Keep all physical robot motion dry-run by default until safety checks pass.
- Never ask the LLM to emit raw motor commands.
- Require stop, timeout, and human override before any live robot movement.
- No contact with targets classified as `MINE` or `UNCERTAIN`.

## P0 Workstreams

### 1. Foundation

Deliverables:

- Create the `safeground/` app skeleton only if/when code work starts.
- Configure `.venv`, package dependencies, and env vars for Cyberwave credentials.
- Define runtime mode flags: `mock`, `simulation`, `live`.
- Default to `mock` or `dry_run=true` for local development and rehearsal.
- Add a simple config object that records robot IDs, sensor IDs, thresholds, capture paths, and safety limits.

Dependencies:

- Cyberwave account/API key.
- Python runtime and package manager selected by the implementation team.
- Decision on frontend path: Streamlit for fastest P0 or Vue/Vite if UI polish is already in progress.

Acceptance criteria:

- App starts without hardware in mock mode.
- Missing credentials fail with a clear message and do not block mock mode.
- Runtime mode is visible in logs and dashboard.

P0 coverage:

- P0.9 Mock mode
- P0.10 Demo script

### 2. Cyberwave Integration

Deliverables:

- Build a small Cyberwave client wrapper for twin discovery, mode selection, and health checks.
- Produce a runtime capability map for Go2, UGV, SO101, and Standard Camera when available.
- Implement one real frame capture path from at least one camera or robot twin.
- Implement mock adapters with the same interface as real adapters.
- Keep real robot commands behind a deterministic adapter and dry-run switch.

Minimum adapter interface:

```python
class RobotAdapter:
    id: str
    role: str

    async def health(self) -> dict: ...
    async def capabilities(self) -> dict: ...
    async def capture_frame(self, sensor_id: str | None = None) -> "FrameRef": ...
    async def stop(self) -> None: ...
```

Live movement is not required for P0 success. If enabled for a smoke test, use only pre-approved bounded actions such as `stop`, `capture_frame`, and one supervised micro-move.

Dependencies:

- Real twin slugs and sensor IDs from the hackathon environment.
- Confirmation of which robot/camera exposes latest-frame or stream access.
- Controller policy/action list for each robot.

Acceptance criteria:

- At least one robot and one camera report online, or mock equivalents are shown clearly.
- Backend captures a frame through SDK or local webcam path.
- Capability map is shown in the dashboard or event log.
- Stop can be sent to any online robot adapter.

P0 coverage:

- P0.1 Cyberwave connection
- P0.2 Frame capture
- P0.8 Safety
- P0.9 Mock mode

### 3. External CV Contract

The CV implementation is external to this plan. SafeGround P0 consumes its output through a strict schema and does not implement training, detector tuning, or model selection.

Required CV response:

```json
{
  "label": "MINE",
  "confidence": 0.82,
  "bbox": [120, 90, 320, 260],
  "evidence": ["round dark mock object visible in center frame"],
  "recommended_action": "REPORT"
}
```

Allowed values:

- `label`: `MINE`, `NOT_MINE`, `UNCERTAIN`
- `recommended_action`: `REPORT`, `SECOND_VIEW`, `HUMAN_REVIEW`
- `confidence`: number from `0.0` to `1.0`
- `bbox`: pixel coordinates `[x_min, y_min, x_max, y_max]`, or `null` if no target is usable
- `evidence`: short strings suitable for the dashboard timeline

Suggested Pydantic model:

```python
from typing import Literal
from pydantic import BaseModel, Field


class ClassificationResult(BaseModel):
    label: Literal["MINE", "NOT_MINE", "UNCERTAIN"]
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: list[int] | None = None
    evidence: list[str] = Field(default_factory=list)
    recommended_action: Literal["REPORT", "SECOND_VIEW", "HUMAN_REVIEW"]
```

SafeGround-owned expectations:

- Validate every CV response with Pydantic before state-machine use.
- Convert invalid output to `UNCERTAIN` plus `HUMAN_REVIEW`.
- Provide fixture JSON files for `MINE`, `NOT_MINE`, `UNCERTAIN`, invalid JSON, low confidence, and missing bbox.
- Provide a fake classifier that reads fixtures deterministically for offline demo.
- Record raw response, normalized response, frame ID, and validation errors in the event store.

External CV dependency expectations:

- The CV owner provides the runtime callable or HTTP endpoint.
- The CV owner owns classifier accuracy, model prompts, detector code, model weights, and training data.
- The CV owner keeps the response compatible with the contract above.
- SafeGround can continue the demo with fixtures if the CV service is unavailable.

Acceptance criteria:

- Valid CV fixture passes schema validation.
- Invalid CV fixture produces a safe `UNCERTAIN`/`HUMAN_REVIEW` path.
- Mock classifier can drive all three labels without hardware or CV service.

P0 coverage:

- P0.3 Classification
- P0.4 Output JSON validated
- P0.9 Mock mode

### 4. Mission State Machine

Deliverables:

- Implement the minimum P0 path:

```text
IDLE -> OBSERVE -> CLASSIFY -> REPORT
```

- Represent P1-ready states without requiring them for P0:

```text
UNCERTAIN -> SECOND_OBSERVATION -> CONSENSUS -> HUMAN_REVIEW
```

- Keep transitions deterministic and schema-driven.
- Ensure every transition emits an event.

P0 transition rules:

- `Start` in `IDLE` creates a mission and enters `OBSERVE`.
- `OBSERVE` captures one frame, stores it, and enters `CLASSIFY`.
- `CLASSIFY` calls external CV or fixture classifier and validates the result.
- `MINE` and `NOT_MINE` enter `REPORT`.
- `UNCERTAIN` enters `REPORT` for P0, with a visible recommendation for `SECOND_VIEW` or `HUMAN_REVIEW`.
- `Stop` from any state enters `MANUAL_STOP`.
- Timeout or adapter failure enters `ERROR_SAFE` and sends stop to relevant adapters.

Acceptance criteria:

- One mission can run from start to report in mock mode.
- One mission can run using a real captured frame if hardware is ready.
- `MINE`, `NOT_MINE`, and `UNCERTAIN` are all visible in the dashboard.
- Stop interrupts the state machine from every state.

P0 coverage:

- P0.3 Classification
- P0.5 State machine
- P0.7 Event log
- P0.8 Safety
- P0.10 Demo script

### 5. Safety Governor

Deliverables:

- Deterministic safety component called before every robot action.
- Manual stop endpoint and visible dashboard control.
- Per-action timeout.
- Allow-list for actions.
- Dry-run default for physical commands.
- Error-safe behavior when stream, telemetry, or adapter calls fail.

Minimum P0 allow-list:

```text
capture_frame
stop
hold_position
```

Optional supervised smoke-test actions:

```text
relative_move_short
rotate_in_place_short
```

Safety invariants:

- No command may contact a target.
- No SO101 interaction with `MINE` or `UNCERTAIN` targets.
- No acrobatics, jumps, backflips, or unconstrained locomotion.
- One active locomotion command per robot at most.
- Stop is issued before and after any live movement.
- Human operator must be able to take over at all times.

Acceptance criteria:

- `Stop All` is reachable from UI and API.
- Timeout converts mission to safe stopped/error state.
- Dry-run logs intended actions without moving hardware.
- Unsafe commands are rejected before adapter execution.

P0 coverage:

- P0.8 Safety
- P0.9 Mock mode

### 6. Event Store And Audit Trail

Deliverables:

- Append-only event log using JSONL or SQLite.
- Store mission ID, event type, timestamp, robot ID, sensor ID, frame path, classification, rationale/evidence, safety decision, and errors.
- Emit events to the dashboard through polling, SSE, or WebSocket.
- Keep captured images in a predictable local folder for replay/debug.

Minimum event types:

```text
MISSION_STARTED
ROBOT_STATUS_UPDATED
FRAME_CAPTURED
CV_RESULT_RECEIVED
CV_RESULT_VALIDATED
STATE_CHANGED
SAFETY_CHECK_PASSED
SAFETY_CHECK_FAILED
MISSION_REPORTED
MISSION_STOPPED
ERROR
```

Acceptance criteria:

- Every mission produces a readable timeline.
- Failed CV, camera, and Cyberwave calls are visible in the log.
- Demo operator can explain what happened from the timeline alone.

P0 coverage:

- P0.7 Event log
- P0.10 Demo script

### 7. Dashboard P0

Deliverables:

- Header with mission state, runtime mode, timer, `Start`, `Stop All`, and `Dry Run`.
- Robot cards for Go2, UGV, SO101, and camera with online/offline, role, sensors, current task, and heartbeat.
- Camera/frame panel with latest frame, bbox, label, confidence, and source.
- Classification card with label, confidence, evidence, and recommended action.
- Timeline/event log.
- Clear fallback banners: mock mode, camera unavailable, CV unavailable, Cyberwave unavailable.

P0 can be built with Streamlit for speed. A more polished Vue/Vite UI is valuable only after the end-to-end loop is stable.

Acceptance criteria:

- Operator can start and stop a mission from the UI.
- Latest frame and classification are visible.
- Robot/camera availability is visible.
- Timeline updates without refreshing the whole app, or with a simple polling fallback.

P0 coverage:

- P0.6 Dashboard
- P0.7 Event log
- P0.8 Safety
- P0.10 Demo script

### 8. Demo Repeatability

Deliverables:

- Scripted P0 demo path using fixtures only.
- Scripted P0 demo path using live camera capture and fake classifier.
- Optional path using live camera plus external CV service.
- One smoke test for Cyberwave connectivity and stop.
- Backup folder with static frames and matching classification fixture responses.

Recommended demo sequence:

1. Open dashboard in mock/dry-run mode.
2. Show robot and camera cards.
3. Run fixture mission for `NOT_MINE`.
4. Run fixture mission for `MINE`.
5. Run fixture mission for `UNCERTAIN`.
6. Show event log and rationale.
7. Press `Stop All`.
8. If hardware is ready, repeat one mission with live frame capture and no live movement.

Acceptance criteria:

- Demo can be repeated three times without changing code.
- Full demo works without hardware, network, or external CV.
- Hardware path is additive, not required for the fallback demo.

P0 coverage:

- P0.9 Mock mode
- P0.10 Demo script

## Recommended Build Order

1. Foundation and config.
2. Mock adapters and fixture classifier.
3. Pydantic models for frame, classification, mission, and event.
4. Event store.
5. State machine with fixture-driven `IDLE -> OBSERVE -> CLASSIFY -> REPORT`.
6. Dashboard connected to mock state and events.
7. Cyberwave discovery and real frame capture.
8. Safety governor around every adapter action.
9. External CV integration behind the same contract.
10. Rehearsal scripts and fallback assets.

This order keeps the demo functional even before hardware and external CV are ready.

## P0 Coverage Matrix

| ID | Requirement | Primary workstream | Acceptance evidence |
| --- | --- | --- | --- |
| P0.1 | Cyberwave connection | Cyberwave Integration | At least one robot and one camera online, or clear mock mode status |
| P0.2 | Frame capture | Cyberwave Integration | Backend stores a captured frame from SDK/local camera or fixture |
| P0.3 | Classification | External CV Contract, State Machine | Fixture or external CV returns `MINE`, `NOT_MINE`, or `UNCERTAIN` |
| P0.4 | Validated JSON output | External CV Contract | Pydantic accepts valid fixture and rejects invalid fixture safely |
| P0.5 | State machine | Mission State Machine | Mission traverses `IDLE -> OBSERVE -> CLASSIFY -> REPORT` |
| P0.6 | Dashboard | Dashboard P0 | UI shows robots, frame, state, classification, and controls |
| P0.7 | Event log | Event Store And Audit Trail | Timeline records every action and error |
| P0.8 | Safety | Safety Governor | Stop and timeout work; unsafe action is rejected |
| P0.9 | Mock mode | Foundation, Mock Adapters, Demo Repeatability | Full flow runs without hardware or external CV |
| P0.10 | Demo script | Demo Repeatability | Operator can repeat a complete mission path |

## Key Dependencies And Gaps

- Real Cyberwave twin slugs, action names, and sensor IDs must be validated onsite.
- Exact Go2/UGV sensor availability is not guaranteed until physical inspection.
- External CV runtime shape is assumed to be callable as a local function or HTTP endpoint; SafeGround only requires the JSON contract.
- Confidence values are operational hints, not calibrated probabilities.
- Live robot movement is not required for P0 and must remain disabled until safety rehearsal passes.

## Done For P0

P0 is done when a presenter can run a mission from the dashboard, capture or load a frame, receive a validated classification, show the state/report/timeline, press stop, and repeat the same flow in mock mode without external services.
