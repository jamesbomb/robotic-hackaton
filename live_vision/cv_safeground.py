"""
cv_safeground.py — il nostro SENSE (VLM hostato Cyberwave) dietro il contratto CV di SafeGround.

Implementa la stessa firma di safeground.cv.MockCVClient:
    async def classify(frame: FrameRef, scenario: str) -> CVClassification

Così è un drop-in nel `cv_client` del MissionRunner — zero modifiche al loro codice:

    from live_vision.cv_safeground import CyberwaveVLMClient
    runner = MissionRunner(config, robot, CyberwaveVLMClient(), event_store, safety)

Sorgente del SENSE = cw_vision.classify() (google/models/gemini-robotics-er-16, detect_boxes).
Più robusto del worker YOLO+HSV: niente taratura colore, regge vista/luce.

Mapping verso l'enum SafeGround (identico alla semantica del loro worker):
    verde   -> NOT_MINE  / REPORT       (SAFE)
    arancio -> MINE      / REPORT        (DANGER)
    nera    -> UNCERTAIN / SECOND_VIEW   (AVOID -> second look)
    niente  -> UNCERTAIN / HUMAN_REVIEW
"""
from __future__ import annotations

import cv2

from safeground.cv import safe_uncertain
from safeground.models import (
    CVClassification,
    ClassificationLabel,
    ClassificationResult,
    FrameRef,
    RecommendedAction,
)

from cw_vision import classify as vlm_classify  # il SENSE hostato

# rischio nostro -> (label SafeGround, azione consigliata). Tieni il PIÙ pericoloso.
_RISK_RANK = {"DANGER": 3, "AVOID": 2, "SAFE": 1}
_MAP = {
    "SAFE":   (ClassificationLabel.NOT_MINE,  RecommendedAction.REPORT),
    "DANGER": (ClassificationLabel.MINE,      RecommendedAction.REPORT),
    "AVOID":  (ClassificationLabel.UNCERTAIN, RecommendedAction.SECOND_VIEW),
}


class CyberwaveVLMClient:
    """SENSE reale dietro il contratto cv_client di SafeGround (VLM hostato Cyberwave)."""

    async def classify(self, frame: FrameRef, scenario: str) -> CVClassification:
        img = cv2.imread(str(frame.path))
        if img is None:
            return safe_uncertain(
                {"frame_path": str(frame.path)},
                [f"frame non leggibile come immagine: {frame.path}"],
            )

        try:
            dets = vlm_classify(img)
        except Exception as exc:  # rete/API giù -> fail-safe verso human review
            return safe_uncertain(
                {"frame_path": str(frame.path), "error": str(exc)},
                [f"VLM hostato non disponibile: {exc}"],
            )

        if not dets:
            return safe_uncertain(
                {"frame_path": str(frame.path), "detections": []},
                ["Nessuna lattina rilevata dal VLM hostato."],
            )

        # bersaglio singolo della missione = il più pericoloso (bias di sicurezza)
        target = max(dets, key=lambda d: (_RISK_RANK[d["risk"]], d["confidence"]))
        label, action = _MAP[target["risk"]]
        x, y, bw, bh = target["_px"]
        bbox = [int(x), int(y), int(x + max(bw, 1)), int(y + max(bh, 1))]

        result = ClassificationResult(
            label=label,
            confidence=float(target["confidence"]),
            bbox=bbox,
            evidence=[
                "SENSE = VLM hostato Cyberwave (gemini-robotics-er, detect_boxes).",
                f"Colore dominante classificato come {target['class']} -> {target['risk']}.",
                f"{len(dets)} lattine nel frame; scelto il bersaglio più pericoloso.",
            ],
            recommended_action=action,
        )
        raw = {
            "model_id": "google/models/gemini-robotics-er-16",
            "detections": [{k: v for k, v in d.items() if not k.startswith("_")} for d in dets],
        }
        return CVClassification(raw_response=raw, result=result, valid=True)
