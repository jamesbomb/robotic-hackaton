#!/usr/bin/env python3
"""
verify_workflow.py — verifica il WORKFLOW INTERO del team col NOSTRO SENSE iniettato.

Fa girare il vero safeground.mission.MissionRunner (la macchina a stati
capture_frame -> CLASSIFY -> REASON/route -> REPORT) usando il NOSTRO
CyberwaveVLMClient al posto di MockCVClient. Le detection del VLM sono iniettate
(deterministico, nessuna rete): cosi' provo che la NOSTRA classificazione
attraversa tutta la pipeline del team e arriva al report giusto.

Uso:  PYTHONPATH=/path/to/repo python live_vision/verify_workflow.py
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import mkdtemp
from uuid import uuid4

import cv2
import numpy as np

import cv_safeground
from cv_safeground import CyberwaveVLMClient
from safeground.adapters import MockRobotAdapter, build_mock_fleet
from safeground.event_store import JsonlEventStore
from safeground.mission import MissionRunner
from safeground.models import ClassificationLabel, FrameRef, MissionState, SafeGroundConfig
from safeground.safety import SafetyGovernor

OK, KO = "\033[92mPASS\033[0m", "\033[91mFAIL\033[0m"
_fails = 0


def check(name, cond, detail=""):
    global _fails
    if not cond:
        _fails += 1
    print(f"  [{OK if cond else KO}] {name}" + (f"  — {detail}" if detail else ""))


# immagine vera (il contenuto non conta: il VLM e' iniettato, ma imread deve riuscire)
_IMG = Path(mkdtemp()) / "frame.jpg"
cv2.imwrite(str(_IMG), np.full((480, 640, 3), 70, np.uint8))


class ImageRobotAdapter(MockRobotAdapter):
    """Come il mock del team, ma capture_frame restituisce un FrameRef su un'immagine vera."""
    async def capture_frame(self, sensor_id: str | None = None) -> FrameRef:
        sid = sensor_id or self.sensor_id
        return FrameRef(frame_id=f"{sid}-{uuid4().hex[:8]}", sensor_id=sid,
                        source="camera", path=_IMG, width=640, height=480)


def _det(risk):
    return {"class": "can", "risk": risk, "confidence": 0.97,
            "center": (120, 140), "_px": (100, 100, 40, 80), "_col": (0, 0, 0)}


def run_mission(injected_dets, scenario="FIELD", with_fleet=False):
    """Esegue il MissionRunner vero col nostro CyberwaveVLMClient (VLM iniettato)."""
    cv_safeground.vlm_classify = lambda _img, _d=injected_dets: list(_d)
    config = SafeGroundConfig(event_log_path=Path(mkdtemp()) / "events.jsonl")
    event_store = JsonlEventStore(config.event_log_path)
    robot = ImageRobotAdapter(config)
    fleet = None
    if with_fleet:
        fleet = {k: ImageRobotAdapter(config, robot_id=v.id, role=v.role, sensor_id=v.sensor_id,
                                      sensors=v.sensors, actions=v.actions, pose=v.pose)
                 for k, v in build_mock_fleet(config).items()}
        robot = fleet["go2"]
    runner = MissionRunner(config, robot, CyberwaveVLMClient(), event_store,
                           SafetyGovernor(config, event_store), fleet=fleet)
    report = asyncio.run(runner.run(scenario))
    states = [e.get("data", {}).get("to") for e in event_store.read()
              if e.get("event_type") == "STATE_CHANGED"] if hasattr(event_store, "read") else []
    return report, states


def main():
    real = cv_safeground.vlm_classify
    print("=== verifica WORKFLOW INTERO (MissionRunner del team + nostro SENSE) ===\n")
    try:
        # verde -> NOT_MINE -> safe_to_contact, report
        r, _ = run_mission([_det("SAFE")])
        check("verde: il workflow arriva a REPORT con NOT_MINE",
              r.classification and r.classification.label == ClassificationLabel.NOT_MINE
              and r.state == MissionState.REPORT, f"label={r.classification and r.classification.label} state={r.state}")
        check("verde: safe_to_contact = True", r.safe_to_contact is True)

        # arancione -> MINE -> NON safe_to_contact
        r, _ = run_mission([_det("DANGER")])
        check("arancio: il workflow arriva a REPORT con MINE",
              r.classification and r.classification.label == ClassificationLabel.MINE
              and r.state == MissionState.REPORT, f"label={r.classification and r.classification.label} state={r.state}")
        check("arancio: safe_to_contact = False (no contatto su MINE)", r.safe_to_contact is False)

        # misto: il piu' pericoloso guida la missione
        r, _ = run_mission([_det("SAFE"), _det("DANGER")])
        check("misto verde+arancio: la missione classifica MINE (il piu' pericoloso)",
              r.classification and r.classification.label == ClassificationLabel.MINE)

        # nera -> UNCERTAIN -> entra nel ramo second-view senza crashare
        r, _ = run_mission([_det("AVOID")], with_fleet=True)
        check("nera: UNCERTAIN attiva il ramo second-view e la missione termina",
              r is not None and r.classification is not None,
              f"label={r.classification and r.classification.label} state={r.state}")
    finally:
        cv_safeground.vlm_classify = real

    print(f"\n{'WORKFLOW INTERO OK' if _fails == 0 else f'{_fails} CHECK FALLITI'}")
    raise SystemExit(1 if _fails else 0)


if __name__ == "__main__":
    main()
