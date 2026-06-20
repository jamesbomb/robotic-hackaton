"""Top-down risk grid from live detections (same logic as live_vision/vision.py)."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

GRID_COLS = 9
GRID_ROWS = 6
RISK_RANK = {"SAFE": 1, "AVOID": 2, "DANGER": 3}
RISK_COL_BGR = {"SAFE": (90, 210, 90), "DANGER": (60, 60, 230), "AVOID": (200, 170, 110)}
AREA_NEAR = 0.045
RANGE_MAX_M = 4.0


def _px_from_detection(detection: dict[str, Any], width: int, height: int) -> tuple[int, int, int, int]:
    px = detection.get("_px")
    if isinstance(px, (list, tuple)) and len(px) >= 4:
        return int(px[0]), int(px[1]), int(px[2]), int(px[3])

    bbox = detection.get("bbox")
    if isinstance(bbox, list) and len(bbox) >= 4:
        if max(bbox) <= 1:
            x = int(bbox[0] * width)
            y = int(bbox[1] * height)
            bw = max(1, int(bbox[2] * width))
            bh = max(1, int(bbox[3] * height))
            return x, y, bw, bh
        x, y, x2, y2 = map(int, bbox[:4])
        return x, y, max(1, x2 - x), max(1, y2 - y)

    center = detection.get("center")
    if isinstance(center, (list, tuple)) and len(center) >= 2:
        cx, cy = int(center[0]), int(center[1])
        return cx - 10, cy - 10, 20, 20

    return width // 2, height // 2, 20, 20


def _center_from_detection(detection: dict[str, Any], width: int, height: int) -> tuple[int, int]:
    center = detection.get("center")
    if isinstance(center, (list, tuple)) and len(center) >= 2:
        return int(center[0]), int(center[1])
    x, y, bw, bh = _px_from_detection(detection, width, height)
    return x + bw // 2, y + bh // 2


def cell_from_detection(detection: dict[str, Any], width: int, height: int) -> tuple[int, int]:
    """Detection -> grid cell (col=bearing, row=distance; near rows at bottom)."""
    cx, _cy = _center_from_detection(detection, width, height)
    col = min(GRID_COLS - 1, max(0, int(cx / max(width, 1) * GRID_COLS)))

    range_m = detection.get("range_m")
    if range_m is not None:
        nearness = 1.0 - min(1.0, max(0.0, float(range_m) / RANGE_MAX_M))
    else:
        x, y, bw, bh = _px_from_detection(detection, width, height)
        nearness = min(1.0, (bw * bh) / float(max(width * height, 1)) / AREA_NEAR)

    row = min(GRID_ROWS - 1, max(0, int(round(nearness * (GRID_ROWS - 1)))))
    return col, row


def update_cells(
    cells: dict[tuple[int, int], str],
    detections: list[dict[str, Any]],
    width: int,
    height: int,
) -> dict[str, int]:
    counts = {"SAFE": 0, "DANGER": 0, "AVOID": 0}
    for detection in detections:
        risk = str(detection.get("risk") or "").upper()
        if risk not in RISK_RANK:
            continue
        counts[risk] += 1
        cell = cell_from_detection(detection, width, height)
        current = cells.get(cell)
        if current is None or RISK_RANK[risk] > RISK_RANK[current]:
            cells[cell] = risk
    return counts


class RiskMapGrid:
    """Mutable top-down risk map shared by vision.py and SafeGround backend."""

    def __init__(self) -> None:
        self.cells: dict[tuple[int, int], str] = {}
        self.frame_width = 640
        self.frame_height = 480
        self.updated_at: datetime | None = None
        self.observer_robot_id: str | None = None
        self.last_counts: dict[str, int] = {"SAFE": 0, "DANGER": 0, "AVOID": 0}
        self.last_frame_id: str | None = None

    def clear(self) -> None:
        self.cells.clear()
        self.last_counts = {"SAFE": 0, "DANGER": 0, "AVOID": 0}
        self.updated_at = datetime.now(UTC)

    def update(
        self,
        detections: list[dict[str, Any]],
        *,
        width: int,
        height: int,
        robot_id: str | None = None,
        frame_id: str | None = None,
    ) -> dict[str, int]:
        self.frame_width = max(1, width)
        self.frame_height = max(1, height)
        if robot_id:
            self.observer_robot_id = robot_id
        if frame_id:
            self.last_frame_id = frame_id
        self.last_counts = update_cells(self.cells, detections, self.frame_width, self.frame_height)
        self.updated_at = datetime.now(UTC)
        return dict(self.last_counts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "grid_cols": GRID_COLS,
            "grid_rows": GRID_ROWS,
            "cells": [
                {"col": col, "row": row, "risk": risk}
                for (col, row), risk in sorted(self.cells.items(), key=lambda item: (item[0][1], item[0][0]))
            ],
            "frame_width": self.frame_width,
            "frame_height": self.frame_height,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "observer_robot_id": self.observer_robot_id,
            "last_frame_id": self.last_frame_id,
            "counts": dict(self.last_counts),
        }
