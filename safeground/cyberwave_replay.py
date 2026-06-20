from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CyberwaveReplayDryRunResult:
    recording_dir: str
    channels: list[str]
    speed: float
    loop: bool
    samples_published: int
    dry_run: bool
    note: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "recording_dir": self.recording_dir,
            "channels": self.channels,
            "speed": self.speed,
            "loop": self.loop,
            "samples_published": self.samples_published,
            "dry_run": self.dry_run,
            "note": self.note,
        }


def replay_cyberwave_recording(
    recording_dir: Path,
    *,
    channels: Sequence[str] | None = None,
    speed: float = 1.0,
    loop: bool = False,
    backend_factory: Callable[[], Any] | None = None,
    replay_fn: Callable[..., Any] | None = None,
) -> CyberwaveReplayDryRunResult:
    path = Path(recording_dir)
    selected_channels = list(channels or ["frames/default"])

    if not path.exists():
        raise FileNotFoundError(f"Cyberwave recording directory not found: {path}")
    if not path.is_dir():
        raise NotADirectoryError(f"Cyberwave recording path must be a directory: {path}")
    if speed < 0:
        raise ValueError("replay speed must be >= 0")
    if not selected_channels or any(not channel.strip() for channel in selected_channels):
        raise ValueError("at least one non-empty replay channel is required")

    if backend_factory is None or replay_fn is None:
        try:
            from cyberwave.data import get_backend
            from cyberwave.data.recording import replay
        except ImportError as exc:
            raise RuntimeError(
                "Cyberwave data replay is unavailable. Install the Cyberwave SDK in this "
                "environment, then retry the dry-run replay."
            ) from exc

        backend_factory = get_backend
        replay_fn = replay

    backend = backend_factory()
    result = replay_fn(
        backend,
        str(path),
        channels=selected_channels,
        speed=speed,
        loop=loop,
    )
    samples_published = int(getattr(result, "samples_published", 0))
    return CyberwaveReplayDryRunResult(
        recording_dir=str(path),
        channels=selected_channels,
        speed=speed,
        loop=loop,
        samples_published=samples_published,
        dry_run=True,
        note=(
            "Cyberwave recording replayed into local data channels only; no robot "
            "motion commands were sent."
        ),
    )
