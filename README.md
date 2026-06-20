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
.venv/bin/python -m safeground.cli --scenario ALL --print-events
```

Useful single-scenario runs:

```bash
.venv/bin/python -m safeground.cli --scenario MINE
.venv/bin/python -m safeground.cli --scenario NOT_MINE
.venv/bin/python -m safeground.cli --scenario UNCERTAIN
.venv/bin/python -m safeground.cli --scenario INVALID
```

The default event log is append-only JSONL at `safeground_runs/events.jsonl`.
Captured mock frames are copied to `safeground_runs/frames/`.

## Verify

```bash
.venv/bin/python -m unittest discover -s tests
```

No hardware, network, Cyberwave credentials, or external CV service are required for
the mock path.
