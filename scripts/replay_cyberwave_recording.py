from __future__ import annotations

import argparse
import json
from pathlib import Path

from safeground.cyberwave_replay import replay_cyberwave_recording


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Dry-run a Cyberwave recording through local model channels.",
    )
    parser.add_argument("recording_dir", type=Path)
    parser.add_argument(
        "--channel",
        action="append",
        dest="channels",
        help="Replay channel; repeat for multiple channels. Defaults to frames/default.",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Replay speed: 1.0 realtime, 2.0 double speed, 0 as fast as possible.",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Loop continuously until interrupted.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = replay_cyberwave_recording(
        args.recording_dir,
        channels=args.channels,
        speed=args.speed,
        loop=args.loop,
    )
    print(json.dumps(result.as_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
