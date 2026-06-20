#!/usr/bin/env python3
"""
verify_compat.py — verifica che la nostra pipeline VLM sia compatibile con SafeGround + l'env Cyberwave.

Tre stadi, dal piu' sicuro (offline) al piu' dipendente (robot):
  1. CONTRATTO  (offline, deterministico): l'adapter produce un CVClassification VALIDO per il loro schema,
                con mapping colore->enum corretto e "il piu' pericoloso vince". Nessuna rete, nessun robot.
  2. SENSE LIVE (rete): il VLM hostato Cyberwave risponde su un'immagine vera.
  3. ENV FRAME  (env): si pesca un frame dal Go2 dell'environment e lo si classifica.

Uso:
  PYTHONPATH=/path/to/repo python live_vision/verify_compat.py            # solo stadio 1+2
  PYTHONPATH=/path/to/repo python live_vision/verify_compat.py --img foto_lattine.jpg
  PYTHONPATH=/path/to/repo python live_vision/verify_compat.py --env <uuid> --twin <uuid>
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import cv2
import numpy as np

import cv_safeground
from cv_safeground import CyberwaveVLMClient
from safeground.cv import MockCVClient
from safeground.models import (
    CVClassification,
    ClassificationLabel,
    FrameRef,
    RecommendedAction,
)

OK, KO, SKIP = "\033[92mPASS\033[0m", "\033[91mFAIL\033[0m", "\033[93mSKIP\033[0m"
_fails = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global _fails
    if not cond:
        _fails += 1
    print(f"  [{OK if cond else KO}] {name}" + (f"  — {detail}" if detail else ""))


def _det(risk: str, x=100, y=100, bw=40, bh=80, conf=0.99, cls="can"):
    return {"class": cls, "risk": risk, "confidence": conf,
            "center": (x + bw // 2, y + bh // 2), "_px": (x, y, bw, bh), "_col": (0, 0, 0)}


def _frame_ref(path: Path) -> FrameRef:
    return FrameRef(frame_id="compat-0", sensor_id="test-cam", source="camera",
                    path=path, width=640, height=480)


# ── STADIO 1: CONTRATTO (offline) ────────────────────────────────────────────
def stage_contract() -> None:
    print("\nSTADIO 1 — CONTRATTO (offline, deterministico)")
    # firma compatibile con lo slot cv_client del MissionRunner
    check("CyberwaveVLMClient ha classify() come MockCVClient",
          asyncio.iscoroutinefunction(CyberwaveVLMClient.classify)
          and asyncio.iscoroutinefunction(MockCVClient.classify))

    img = Path("/tmp/_compat_frame.png")
    cv2.imwrite(str(img), np.full((480, 640, 3), 60, np.uint8))
    client = CyberwaveVLMClient()
    real_classify = cv_safeground.vlm_classify

    cases = [
        ("verde -> NOT_MINE/REPORT",    [_det("SAFE")],   ClassificationLabel.NOT_MINE,  RecommendedAction.REPORT),
        ("arancio -> MINE/REPORT",      [_det("DANGER")], ClassificationLabel.MINE,      RecommendedAction.REPORT),
        ("nera -> UNCERTAIN/SECOND_VIEW", [_det("AVOID")], ClassificationLabel.UNCERTAIN, RecommendedAction.SECOND_VIEW),
        ("niente -> UNCERTAIN/HUMAN_REVIEW", [],          ClassificationLabel.UNCERTAIN, RecommendedAction.HUMAN_REVIEW),
        ("misto SAFE+DANGER -> il piu' pericoloso (MINE)",
         [_det("SAFE", x=10), _det("DANGER", x=300)], ClassificationLabel.MINE, RecommendedAction.REPORT),
    ]
    try:
        for name, dets, want_label, want_action in cases:
            cv_safeground.vlm_classify = lambda _img, _d=dets: list(_d)
            res = asyncio.run(client.classify(_frame_ref(img), "FIELD"))
            ok = (isinstance(res, CVClassification) and res.result.label == want_label
                  and res.result.recommended_action == want_action)
            check(name, ok, f"-> {res.result.label}/{res.result.recommended_action}")
            # bbox valido secondo il loro validator (x_min<x_max, y_min<y_max)
            if dets and res.result.bbox:
                b = res.result.bbox
                check(f"   bbox valido {b}", b[0] < b[2] and b[1] < b[3])
    finally:
        cv_safeground.vlm_classify = real_classify

    # frame illeggibile -> fail-safe, non crash
    res = asyncio.run(client.classify(_frame_ref(Path("/tmp/_nope.png")), "FIELD"))
    check("frame illeggibile -> UNCERTAIN (fail-safe, no crash)",
          res.result.label == ClassificationLabel.UNCERTAIN and not res.valid)


# ── STADIO 2: SENSE LIVE (rete) ──────────────────────────────────────────────
def stage_sense(img_path: str | None) -> None:
    print("\nSTADIO 2 — SENSE LIVE (rete, VLM hostato Cyberwave)")
    if not img_path:
        print(f"  [{SKIP}] nessuna immagine (--img foto.jpg per provare il VLM su lattine vere)")
        return
    img = cv2.imread(img_path)
    if img is None:
        check("immagine leggibile", False, img_path); return
    try:
        from cw_vision import classify as vlm
        dets = vlm(img)
        check("VLM hostato risponde", True, f"{len(dets)} detection")
        for d in dets:
            print(f"      - {d['class']:8s} {d['risk']:6s} conf {d['confidence']}")
    except Exception as exc:
        check("VLM hostato raggiungibile", False, str(exc))


# ── STADIO 3: ENV FRAME (environment Cyberwave) ──────────────────────────────
def stage_env(env_uuid: str | None, twin_uuid: str | None) -> None:
    print("\nSTADIO 3 — ENV FRAME (frame dal Go2 dell'environment)")
    if not (env_uuid or twin_uuid):
        print(f"  [{SKIP}] nessun env/twin (--env <uuid> --twin <uuid> per provare il frame del Go2)")
        return
    try:
        from cyberwave import Cyberwave
        from cw_vision import _api_key, classify as vlm
        cw = Cyberwave(api_key=_api_key())
        try:
            cw.affect("simulation")
        except Exception:
            pass
        dog = cw.twin(twin_id=twin_uuid, environment_id=env_uuid)   # 403 se la key non ha accesso
        b = dog.get_latest_frame() if hasattr(dog, "get_latest_frame") else None
        if not b:
            check("frame dal Go2", False, "stream spento / nessun frame (attiva SIMULATE o LIVE nel viewer)")
            return
        frame = cv2.imdecode(np.frombuffer(b, np.uint8), cv2.IMREAD_COLOR)   # bytes JPEG -> BGR
        check("frame decodificato (BGR)", frame is not None,
              f"{len(b)} byte -> {getattr(frame, 'shape', 'None')}")
        if frame is not None:
            check("frame del Go2 classificabile dal nostro VLM", True, f"{len(vlm(frame))} detection")
    except Exception as exc:
        check("accesso/connessione env/twin", False, repr(exc)[:160])


def main() -> None:
    a = sys.argv
    img = a[a.index("--img") + 1] if "--img" in a else None
    env = a[a.index("--env") + 1] if "--env" in a else None
    twin = a[a.index("--twin") + 1] if "--twin" in a else None
    print("=== verifica compatibilita' VLM <-> SafeGround <-> Cyberwave ===")
    stage_contract()
    stage_sense(img)
    stage_env(env, twin)
    print(f"\n{'TUTTO COMPATIBILE' if _fails == 0 else f'{_fails} CHECK FALLITI'}")
    sys.exit(1 if _fails else 0)


if __name__ == "__main__":
    main()
