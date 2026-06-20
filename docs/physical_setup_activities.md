# SafeGround Physical Setup Activities

## Goal

Prepare the physical demo so the P0 mission can run safely and repeatably with robot hardware when available, while preserving a complete mock fallback when hardware, network, camera, or external CV are not ready.

This checklist is intentionally operational. It should be used onsite before the final demo and during every rehearsal.

## Operating Principles

- Use only inert mock objects and controlled props.
- Keep the public outside the camera capture area where possible.
- Start in mock mode, then live camera with robots stopped, then supervised hardware smoke tests.
- Treat the CV system as an external dependency. Physical setup only verifies frame quality, fixture coverage, and expected mock-classifier scenarios.
- Do not move robots until stop paths, timeout behavior, and human takeover are tested.
- Do not use SO101 for P0 movement near suspicious objects; SO101 remains P2/wow-factor unless explicitly cleared.

## 1. Credentials And Environment

Before touching hardware:

- [ ] Confirm Cyberwave account access.
- [ ] Confirm API key or login flow for the demo machine.
- [ ] Confirm network access in the demo venue.
- [ ] Confirm backup internet path, for example phone hotspot.
- [ ] Confirm repository and runtime are available on the demo machine.
- [ ] Confirm `.env` or equivalent config contains only local/demo credentials.
- [ ] Confirm runtime mode starts in `mock` or `dry_run=true`.
- [ ] Confirm static frame fixtures and classification fixtures are present locally.
- [ ] Confirm external CV owner has provided the expected interface or endpoint, if it will be used live.
- [ ] Confirm external CV failure does not block the fixture/mock-classifier path.

Exit criteria:

- The dashboard can open in mock mode without Cyberwave hardware.
- A fixture mission can run end-to-end.
- `Stop All` is visible before any robot is powered for movement.

## 2. Demo Area Setup

Area:

- [ ] Mark a bounded demo zone with tape, cones, mats, or table borders.
- [ ] Mark an operator zone separate from robot movement.
- [ ] Mark a no-entry buffer for spectators.
- [ ] Define a simple grid or relative coordinate system, for example `A1`, `A2`, `B1`, `B2`.
- [ ] Photograph the empty area for reset reference.
- [ ] Remove loose cables, bags, reflective clutter, and tripping hazards.
- [ ] Confirm there is enough clearance for Go2/UGV if any movement is tested.
- [ ] Confirm lighting is stable from the camera viewpoint.
- [ ] Avoid backlight, glare, harsh shadows, and highly reflective props.
- [ ] Confirm camera framing does not capture audience faces where possible.

Mock objects:

- [ ] Prepare at least 3 clearly suspicious mine-like props.
- [ ] Prepare at least 3 clearly innocuous props.
- [ ] Prepare at least 2 ambiguous props.
- [ ] Prepare 1 partially occluded object.
- [ ] Prepare 1 difficult-lighting case if time allows.
- [ ] Label props physically on the underside or in a hidden operator sheet.
- [ ] Keep all props inert, soft, and safe to touch by humans.
- [ ] Ensure no prop resembles a real explosive too closely for public safety messaging.

Exit criteria:

- The area can be reset to the same layout in under 2 minutes.
- Three P0 classification cases are visible: `MINE`, `NOT_MINE`, `UNCERTAIN`.
- A presenter can explain that all objects are mock/inert.

## 3. Camera P0 Setup

Preferred order:

1. Standard Camera or fixed webcam.
2. UGV camera while robot remains stationary.
3. Go2 onboard camera while robot remains stationary.
4. Additional cameras only after P0 is stable.

Checklist:

- [ ] Mount or place the primary camera so it cannot shift during the demo.
- [ ] Verify the whole target area is in frame.
- [ ] Verify target size is large enough for bbox display.
- [ ] Capture one clean frame for `MINE`.
- [ ] Capture one clean frame for `NOT_MINE`.
- [ ] Capture one clean frame for `UNCERTAIN`.
- [ ] Save fallback images locally.
- [ ] Record source name: camera twin, local device ID, or file fixture.
- [ ] Check frame latency and refresh behavior.
- [ ] Check exposure/focus after moving props.
- [ ] Confirm the dashboard can display latest frame or fallback image.
- [ ] Confirm bbox overlay coordinates match the displayed image size.

Frame quality rules:

- Use high-contrast props.
- Keep target centered when possible.
- Avoid edge distortion on wide-angle cameras.
- Prefer stable camera over moving robot camera for P0 reliability.
- If a live frame is blurred or occluded, classify as `UNCERTAIN` or use fixture fallback.

Exit criteria:

- At least one live or fallback camera source can produce a frame on demand.
- The saved fallback frame set covers all three labels.
- The dashboard can show frame, bbox, label, and confidence.

## 4. Robot Readiness

### Go2

- [ ] Confirm exact variant.
- [ ] Confirm battery level.
- [ ] Confirm network connectivity.
- [ ] Confirm Cyberwave twin online.
- [ ] Confirm available sensors: camera, LiDAR, pose, joint states, occupancy map if present.
- [ ] Confirm available actions: stop, capture, relative move, rotate, waypoint if present.
- [ ] Confirm physical/manual stop or operator controller access.
- [ ] Confirm Go2 can stand or hold safely in the demo area.
- [ ] Keep locomotion disabled until safety rehearsal passes.

P0 use:

- Camera or robot card status only.
- Optional stationary frame capture.
- Base movement contract in mock/simulation.
- At most one supervised live micro-movement after stop, health and frame checks pass.

### UGV Beast

- [ ] Confirm battery level.
- [ ] Confirm Cyberwave twin online.
- [ ] Confirm camera availability.
- [ ] Confirm pan/tilt availability if present.
- [ ] Confirm odometry/pose availability if present.
- [ ] Confirm action list: stop, capture, relative move, rotate, waypoint if present.
- [ ] Confirm wheels/tracks have clear floor contact and no cable risk.
- [ ] Keep movement disabled until stop and timeout are tested.

P0 use:

- Stationary camera capture or robot card status.
- Optional pan/tilt only if bounded and supervised.
- Base movement contract in mock/simulation; live movement only as supervised smoke test.

### SO101

- [ ] Confirm whether SO101 is physically present.
- [ ] Confirm it is not needed for P0 success.
- [ ] Confirm home pose and emergency stop if used for any optional demo.
- [ ] Confirm workspace is separate from suspected target props.
- [ ] Confirm payload/marker is soft, light, and safe.
- [ ] Do not use SO101 to touch `MINE` or `UNCERTAIN` targets.

P0 use:

- Robot card can show offline, mock, or idle status.
- Physical marker behavior is P2, not P0.

### Standard Camera

- [ ] Confirm USB/IP camera is recognized by the OS or Cyberwave.
- [ ] Confirm stable mounting.
- [ ] Confirm resolution/FPS.
- [ ] Confirm frame capture path.
- [ ] Confirm fallback images if camera feed fails.

Exit criteria:

- At least one robot and one camera are online, or mock status clearly substitutes them for fallback.
- Stop behavior is known for every powered robot.
- No robot is allowed to move without an assigned safety operator.

## 5. Safety Rehearsal

Roles:

- [ ] Assign one presenter/operator.
- [ ] Assign one safety owner with authority to stop the demo.
- [ ] Assign one hardware spotter if robots move.
- [ ] Assign one CV owner/contact if external CV is used live.

Software checks:

- [ ] Press `Stop All` before mission start and confirm safe state.
- [ ] Start mock mission, press `Stop All`, confirm mission stops.
- [ ] Simulate camera failure and confirm safe error state.
- [ ] Simulate external CV timeout and confirm `UNCERTAIN`/`HUMAN_REVIEW` or safe error path.
- [ ] Simulate invalid CV JSON and confirm schema validation catches it.
- [ ] Confirm timeout is shorter than any risky physical behavior.
- [ ] Confirm dry-run logs intended robot actions without movement.

Physical checks:

- [ ] Identify physical/manual stop for each robot.
- [ ] Confirm operator can reach or trigger stop without entering robot path.
- [ ] Verify robot starts from a known pose.
- [ ] Verify robot path is clear.
- [ ] If movement is tested, execute only one short supervised movement.
- [ ] Stop before and after frame capture or movement.
- [ ] Abort if robot drifts, slips, loses network, or ignores stop.

Exit criteria:

- Manual stop and software stop have both been demonstrated.
- The safety owner agrees whether live movement is allowed.
- If there is any doubt, the demo remains camera-only or mock-only.

## 6. Demo Rehearsal Path

Run these in order. Do not skip ahead to live movement.

### Rehearsal A: Full Mock

- [ ] Open dashboard.
- [ ] Confirm mode shows `mock` or `dry_run`.
- [ ] Run `NOT_MINE` fixture mission.
- [ ] Run `MINE` fixture mission.
- [ ] Run `UNCERTAIN` fixture mission.
- [ ] Confirm timeline records each mission.
- [ ] Press `Stop All`.
- [ ] Reset dashboard state.

Success:

- Complete P0 story works without hardware, network, or external CV.

### Rehearsal B: Live Camera, Mock Classifier

- [ ] Switch frame source to live camera.
- [ ] Keep robot movement disabled.
- [ ] Capture frame from the demo area.
- [ ] Route result through fake classifier or selected fixture.
- [ ] Confirm dashboard shows live frame plus deterministic classification.
- [ ] Press `Stop All`.

Success:

- Physical scene appears in dashboard while classification remains deterministic.

### Rehearsal C: Live Camera, External CV

- [ ] Confirm external CV owner is ready.
- [ ] Send one live or saved frame to external CV.
- [ ] Validate response with the SafeGround schema.
- [ ] Confirm invalid/timeout path is safe.
- [ ] Confirm fallback to fixture classifier is one command/config change.

Success:

- External CV is integrated only through the contract and can be bypassed quickly.

### Rehearsal D: Hardware Smoke Test

Only if safety rehearsal passed:

- [ ] Power one robot.
- [ ] Confirm twin online.
- [ ] Send stop command.
- [ ] Capture frame while robot is stationary.
- [ ] Optionally execute one pre-approved short movement.
- [ ] Send stop again.
- [ ] Confirm event log captured all actions.

Success:

- Hardware proves Cyberwave connectivity without becoming a demo dependency.

## 7. Fallback Decisions

Use this table during the demo. Do not improvise a risky hardware workaround.

| Failure | Immediate action | Demo fallback |
| --- | --- | --- |
| Cyberwave login fails | Keep `mock` mode | Run fixture demo |
| Robot twin offline | Mark robot offline in UI | Use camera/fixtures |
| Camera feed fails | Switch to saved frame | Run fixture classifier |
| External CV fails | Disable external CV | Use fake classifier fixtures |
| Network unstable | Stop robots | Use local mock mode |
| Robot ignores command | Physical/manual stop | Continue with no movement |
| Lighting degrades | Reposition lamp/props once | Use saved frames |
| Bbox overlay mismatch | Disable overlay or use saved screenshot | Explain classification card and log |
| Dashboard live updates fail | Refresh or use static timeline | Narrate from event log |
| SO101 unavailable | Mark digital-only | Do not attempt marker demo |

## 8. Final Pre-Demo Checklist

Run 15-30 minutes before presenting:

- [ ] Mock demo passes.
- [ ] Live camera frame capture passes or fallback frames are loaded.
- [ ] External CV path is either passing or deliberately disabled.
- [ ] Robot cards show correct online/offline/mock status.
- [ ] Stop button is visible and tested.
- [ ] Event log is empty or reset for the demo.
- [ ] Demo props are in known positions.
- [ ] Safety owner is assigned.
- [ ] Presenter knows the fallback decision table.
- [ ] Backup screenshots/video are available if the full system cannot run.

## P0 Physical Coverage

| ID | Physical activity that supports it |
| --- | --- |
| P0.1 | Credentials, Cyberwave twin checks, robot readiness |
| P0.2 | Camera setup, live/fallback frame capture |
| P0.3 | Fixture frame set and external CV contract rehearsal |
| P0.4 | Invalid JSON and timeout simulation during safety rehearsal |
| P0.5 | Mock and live-camera rehearsal paths |
| P0.6 | Dashboard pre-demo check |
| P0.7 | Event log verification in every rehearsal |
| P0.8 | Software stop, physical stop, timeout, and safety-owner checks |
| P0.9 | Full mock rehearsal and local fixture fallback |
| P0.10 | Ordered rehearsal path and final pre-demo checklist |

## Stop Conditions

Stop the physical demo and switch to mock/fallback if any of these occur:

- A robot moves outside the marked area.
- Stop command or manual stop is not confirmed.
- Public enters the robot path.
- Robot loses network while movement is enabled.
- Camera or telemetry loss prevents the operator from understanding state.
- External CV output is invalid repeatedly and fallback is not enabled.
- Any team member is unsure whether the next physical action is safe.

## Done

The physical setup is ready when the team can run the full mock path, capture or display a usable frame, demonstrate stop behavior, explain every fallback, and decide explicitly whether hardware movement is enabled or disabled for the final demo.
