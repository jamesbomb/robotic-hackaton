# SafeGround P0 Prototype

Minimal mock-first SafeGround P0 loop:

```text
Frame capture -> CV contract validation -> Mission decision -> JSONL audit report
```

Computer vision is intentionally external. This prototype owns only the integration
contract, Pydantic validation, deterministic fixtures, and a fixture-backed mock CV
client.

## Run The Mock Demo

Use the existing project virtualenv:

```bash
.venv/bin/python -m safeground.cli --scenario FIELD --print-events
```

The main test scenario is one shared field containing orange cans (`MINE`),
black cans (`UNCERTAIN`), and green cans (`NOT_MINE`) scattered together.
Useful diagnostic fixture runs:

```bash
.venv/bin/python -m safeground.cli --scenario FIELD
.venv/bin/python -m safeground.cli --scenario MINE
.venv/bin/python -m safeground.cli --scenario NOT_MINE
.venv/bin/python -m safeground.cli --scenario UNCERTAIN
.venv/bin/python -m safeground.cli --scenario INVALID
```

## Chat And Voice Commands

Chat commands are interpreted into safe structured intents before they reach the
mission runner. Stop commands bypass planning and call the deterministic stop path.

```bash
.venv/bin/python -m safeground.cli --command "ispeziona il campo in cerca di mine" --print-events
.venv/bin/python -m safeground.cli --command "ferma tutto"
```

Voice input is secondary and reuses the same command path after Whisper
transcription. It requires the optional `openai-whisper` package in the project
venv:

```bash
.venv/bin/pip install openai-whisper
.venv/bin/python -m safeground.cli --voice-wav input.wav --whisper-model tiny
```

## SO-101 Manual Takeover

The ops console exposes bounded human takeover controls for the SO-101 mock arm:
`home`, `hold_position`, small `nudge_joint` steps, and a prevalidated
`place_safe_marker` preset for `NOT_MINE` targets only. The matching API endpoint
is `POST /api/robots/so101/manual-arm`; every command requires
`operator_confirmed=true` and is written to the JSONL audit log.

## P0 Base Movements

Mobile robots expose bounded base movement in mock/simulation P0:
`move_forward`, `move_backward`, `strafe_left`, `strafe_right`, `rotate_left`,
and `rotate_right`. Use
`POST /api/robots/go2/move` or the dashboard panel. Each command requires
`operator_confirmed=true`, is wrapped by stop-before/stop-after sequencing, and
is capped at 0.5 m or 15 degrees.

Dashboard shortcuts are available from the Web UI help overlay with `?`.
Enable `Keyboard Drive` in `Base Movement P0` before using `W/A/S/D` or arrow
keys for Go2 micro-movements. `Shift+A` and `Shift+D` strafe laterally.
`Space` and `Esc` trigger `Stop All`,
`Ctrl/Cmd+K` focuses the command palette, `M/N/U` mark the latest camera object,
and `R`/`C` plan or clear the scout route.

The full movement capability map for Go2, UGV Beast, and SO-101 is documented
in `docs/robot_movement_capability_map.md`.

## Runtime Switching

Use the dashboard `Safety` panel or `POST /api/runtime` to switch between
`mock`, `simulation`, and `live`, and to toggle `dry_run`. Live non-dry-run
requires `operator_confirmed=true` and is audited. Current Python adapters are
still mock-safe until Cyberwave live adapters are wired.

For Cyberwave digital twin testing, select `simulation` in `Safety -> Runtime`
and keep dry-run enabled. This matches the Cyberwave SDK pattern
`cw.affect("simulation")`.

## Robot Activation

The `Robot Activation` panel discovers local Cyberwave twins. Every discovered
digital twin can be marked `Ready Virtual` so the Web UI can operate against the
simulation/dashboard twin even when no local physical adapter exists. `Arm
Physical` remains restricted to robots with a SafeGround adapter in
`live + dry_run=false`. Base movement can target `virtual`, `physical`, `both`,
or `auto`; physical targets require an armed robot and remain bounded.

## Collaborator Mac Setup

From a fresh macOS machine:

```bash
xcode-select --install
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install python@3.13 node git
git clone <REPO_URL> safeground
cd safeground
python3.13 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -e . cyberwave
cd frontend && npm install && cd ..
.venv/bin/python -m unittest discover -s tests
cd frontend && npm run build && cd ..
```

Run backend and frontend:

```bash
.venv/bin/uvicorn safeground.api.server:app --reload
```

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173`, then use `Robot Activation -> Ready Virtual` for
the discovered digital twins.

## Assisted Object Pickup

The dashboard includes an `Object Pickup Workflow` for supervised record/replay:
Go2 low posture is recorded, SO-101 human takeover commands are captured with
video references, and `Finish / Save` stores a reusable template. YOLO automation
is intentionally deferred until the recorded sequence is validated on `NOT_MINE`
objects with operator confirmation.

## Cyberwave Replay Dry Run

Use `.venv/bin/python -m safeground.cli --replay-recording <recording-dir>` to
replay recorded Cyberwave frames into the local model channels without starting a
mission or sending robot commands. See `docs/commands.md` for the YOLO worker
example.

The default event log is append-only JSONL at `safeground_runs/events.jsonl`.
Captured mock frames are copied to `safeground_runs/frames/`.

## Verify

```bash
.venv/bin/python -m unittest discover -s tests
```

No hardware, network, Cyberwave credentials, or external CV service are required for
the mock path.
