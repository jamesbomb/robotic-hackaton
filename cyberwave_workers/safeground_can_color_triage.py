from __future__ import annotations

import os
import time
from typing import Any

import numpy as np


MODEL_ID = os.getenv("SAFEGROUND_YOLO_MODEL_ID", "yoloe-26n-seg.pt")
PRIMARY_TWIN_UUID = os.getenv(
    "SAFEGROUND_PRIMARY_TWIN_UUID",
    "8a40ed9f-349c-44d2-98c0-3a2282134839",  # UGV Beast
)
SECOND_LOOK_TWIN_UUID = os.getenv(
    "SAFEGROUND_SECOND_LOOK_TWIN_UUID",
    "758bee49-6668-4733-80f8-da1c0a7134b2",  # Unitree Go2
)
DETECTION_CLASSES = [
    item.strip()
    for item in os.getenv(
        "SAFEGROUND_CAN_CLASSES",
        "can,soda can,tin can,bottle,cup",
    ).split(",")
    if item.strip()
]
DETECTION_CONFIDENCE = float(os.getenv("SAFEGROUND_DETECTION_CONFIDENCE", "0.4"))
FRAME_FPS = float(os.getenv("SAFEGROUND_FRAME_FPS", "3"))
EMIT_COOLDOWN_S = float(os.getenv("SAFEGROUND_EMIT_COOLDOWN_S", "1.0"))


if MODEL_ID == "yoloe-26n-seg.pt":
    yolo = cw.models.load("yoloe-26n-seg.pt")  # type: ignore[name-defined]  # noqa: F821
else:
    yolo = cw.models.load(MODEL_ID)  # type: ignore[name-defined]  # noqa: F821
_last_emit: dict[str, tuple[float, str]] = {}


def _predict(frame: Any, ctx: Any) -> list[Any]:
    twin_uuid = getattr(ctx, "twin_uuid", None)
    kwargs: dict[str, Any] = {
        "confidence": DETECTION_CONFIDENCE,
        "classes": DETECTION_CLASSES,
    }
    if twin_uuid:
        kwargs["twin_uuid"] = twin_uuid

    try:
        result = yolo.predict(frame, **kwargs)
    except TypeError:
        kwargs.pop("twin_uuid", None)
        try:
            result = yolo.predict(frame, **kwargs)
        except TypeError:
            result = yolo.predict(frame)

    detections = getattr(result, "detections", result)
    if detections is None:
        return []
    return list(detections)


def _field(obj: Any, *names: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        for name in names:
            if name in obj:
                return obj[name]
        return default

    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
    return default


def _coerce_bbox(value: Any) -> list[int] | None:
    if value is None:
        return None
    if hasattr(value, "xyxy"):
        value = value.xyxy
    if all(hasattr(value, attr) for attr in ("x_min", "y_min", "x_max", "y_max")):
        return [
            int(value.x_min),
            int(value.y_min),
            int(value.x_max),
            int(value.y_max),
        ]
    if isinstance(value, np.ndarray):
        value = value.tolist()
    if isinstance(value, (list, tuple)) and len(value) >= 4:
        flat = value[0] if len(value) == 1 and isinstance(value[0], (list, tuple)) else value
        if len(flat) >= 4:
            x_min, y_min, x_max, y_max = flat[:4]
            return [int(x_min), int(y_min), int(x_max), int(y_max)]
    return None


def _best_detection(detections: list[Any]) -> tuple[Any, float, list[int]] | None:
    best: tuple[Any, float, list[int]] | None = None
    for detection in detections:
        confidence = float(_field(detection, "confidence", "score", "conf", default=0.0) or 0.0)
        bbox = _coerce_bbox(_field(detection, "bbox", "box", "xyxy"))
        if bbox is None:
            continue
        if best is None or confidence > best[1]:
            best = (detection, confidence, bbox)
    return best


def _to_rgb_array(frame: Any) -> np.ndarray:
    if hasattr(frame, "convert"):
        return np.asarray(frame.convert("RGB"))
    if isinstance(frame, np.ndarray):
        array = frame
    else:
        array = np.asarray(frame)

    if array.ndim == 2:
        return np.stack([array, array, array], axis=-1)
    if array.ndim == 3 and array.shape[2] >= 3:
        return array[:, :, :3]
    raise ValueError("unsupported frame shape for color triage")


def _crop_frame(frame: Any, bbox: list[int]) -> np.ndarray | None:
    array = _to_rgb_array(frame)
    height, width = array.shape[:2]
    x_min, y_min, x_max, y_max = bbox
    x_min = max(0, min(width - 1, x_min))
    x_max = max(0, min(width, x_max))
    y_min = max(0, min(height - 1, y_min))
    y_max = max(0, min(height, y_max))
    if x_min >= x_max or y_min >= y_max:
        return None
    return array[y_min:y_max, x_min:x_max, :]


def _hue_scores(rgb: np.ndarray) -> dict[str, float]:
    pixels = rgb.reshape(-1, 3).astype(np.float32) / 255.0
    red = pixels[:, 0]
    green = pixels[:, 1]
    blue = pixels[:, 2]
    max_channel = pixels.max(axis=1)
    min_channel = pixels.min(axis=1)
    diff = max_channel - min_channel
    saturation = np.divide(diff, max_channel, out=np.zeros_like(diff), where=max_channel > 0)

    hue = np.zeros_like(max_channel)
    red_mask = (max_channel == red) & (diff > 0)
    green_mask = (max_channel == green) & (diff > 0)
    blue_mask = (max_channel == blue) & (diff > 0)
    hue[red_mask] = ((green[red_mask] - blue[red_mask]) / diff[red_mask]) % 6
    hue[green_mask] = ((blue[green_mask] - red[green_mask]) / diff[green_mask]) + 2
    hue[blue_mask] = ((red[blue_mask] - green[blue_mask]) / diff[blue_mask]) + 4
    hue *= 60.0

    vivid = (saturation > 0.25) & (max_channel > 0.18)
    return {
        "green": float(np.mean(vivid & (hue >= 70.0) & (hue <= 170.0))),
        "orange": float(np.mean(vivid & (hue >= 5.0) & (hue <= 45.0))),
        "black": float(np.mean(max_channel < 0.18)),
    }


def _classify_color(roi: np.ndarray) -> tuple[str, dict[str, float]]:
    rgb_scores = _hue_scores(roi)
    bgr_scores = _hue_scores(roi[:, :, ::-1])
    scores = rgb_scores if max(rgb_scores.values()) >= max(bgr_scores.values()) else bgr_scores

    if scores["black"] >= 0.45:
        return "black", scores
    if scores["green"] >= 0.12 and scores["green"] >= scores["orange"]:
        return "green", scores
    if scores["orange"] >= 0.12:
        return "orange", scores
    return "unknown", scores


def _result_for_color(color: str) -> tuple[str, str, str]:
    if color == "green":
        return "NOT_MINE", "REPORT", "SAFE"
    if color == "orange":
        return "MINE", "REPORT", "DANGER"
    if color == "black":
        return "UNCERTAIN", "SECOND_VIEW", "DOUBT"
    return "UNCERTAIN", "HUMAN_REVIEW", "UNKNOWN"


def _publish_if_changed(twin_uuid: str, event_key: str, payload: dict[str, Any]) -> None:
    now = time.monotonic()
    previous = _last_emit.get(twin_uuid)
    if previous and previous[1] == event_key and now - previous[0] < EMIT_COOLDOWN_S:
        return

    _last_emit[twin_uuid] = (now, event_key)
    cw.publish_event(twin_uuid, "safeground_can_triage", payload)  # type: ignore[name-defined]  # noqa: F821


def _handle_frame(twin_uuid: str, robot_role: str, frame: Any, ctx: Any) -> None:
    detection = _best_detection(_predict(frame, ctx))
    if detection is None:
        return

    raw_detection, detection_confidence, bbox = detection
    roi = _crop_frame(frame, bbox)
    if roi is None:
        return

    color, color_scores = _classify_color(roi)
    label, recommended_action, risk_state = _result_for_color(color)
    confidence = round(min(0.99, max(detection_confidence, max(color_scores.values()))), 3)
    event_key = f"{label}:{recommended_action}:{bbox}"
    payload = {
        "label": label,
        "confidence": confidence,
        "bbox": bbox,
        "evidence": [
            f"YOLO {MODEL_ID} detected a can-like object.",
            f"Dominant can color classified as {color}.",
        ],
        "recommended_action": recommended_action,
        "risk_state": risk_state,
        "color": color,
        "color_scores": color_scores,
        "model_id": MODEL_ID,
        "detection_label": _field(raw_detection, "label", "class_name", "name", default="can"),
        "detection_confidence": detection_confidence,
        "frame_ts": getattr(ctx, "timestamp", None),
        "sensor": getattr(ctx, "sensor_name", None),
        "robot_role": robot_role,
    }
    if color == "black":
        payload["second_look_twin_uuid"] = SECOND_LOOK_TWIN_UUID
        payload["second_look_reason"] = "Black can is treated as doubt; verify with another robot."

    _publish_if_changed(twin_uuid, event_key, payload)


@cw.on_frame(PRIMARY_TWIN_UUID, fps=FRAME_FPS)  # type: ignore[name-defined]  # noqa: F821
def safeground_primary_can_triage(frame: Any, ctx: Any) -> None:
    _handle_frame(PRIMARY_TWIN_UUID, "Primary Scout", frame, ctx)


@cw.on_frame(SECOND_LOOK_TWIN_UUID, fps=FRAME_FPS)  # type: ignore[name-defined]  # noqa: F821
def safeground_second_look_can_triage(frame: Any, ctx: Any) -> None:
    _handle_frame(SECOND_LOOK_TWIN_UUID, "Verification Scout", frame, ctx)
