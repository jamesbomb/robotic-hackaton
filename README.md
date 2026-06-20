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
.venv/bin/python -m safeground.cli --command "ispeziona il campo con lattine arancioni nere e verdi" --print-events
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
`move_forward`, `move_backward`, `rotate_left`, and `rotate_right`. Use
`POST /api/robots/go2/move` or the dashboard panel. Each command requires
`operator_confirmed=true`, is wrapped by stop-before/stop-after sequencing, and
is capped at 0.5 m or 15 degrees.

The default event log is append-only JSONL at `safeground_runs/events.jsonl`.
Captured mock frames are copied to `safeground_runs/frames/`.

## Verify

```bash
.venv/bin/python -m unittest discover -s tests
```

No hardware, network, Cyberwave credentials, or external CV service are required for
the mock path.
