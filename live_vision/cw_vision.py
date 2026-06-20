#!/usr/bin/env python3
"""
cw_vision.py — il SENSE robusto: detection+classificazione via VLM HOSTATO Cyberwave.

Nessun download, nessuna API key separata (la CYBERWAVE_API_KEY del robot).
Modello: gemini-robotics-er (box grounding da prompt). Ritorna le detection nel
NOSTRO formato (stesso di vision.py) -> intercambiabile con la CV-colore.

  green  -> SAFE   (lascia)
  orange -> DANGER (rimuovi)
  black  -> AVOID  (instabile -> traccia)
"""
import base64, os, cv2
from pathlib import Path
from cyberwave import Cyberwave

# key: il file .cwkey VINCE sull'env (cosi' una CYBERWAVE_API_KEY stale nell'env non rompe)
def _load_repo_env() -> None:
    if os.environ.get("CYBERWAVE_API_KEY"):
        return
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return
    try:
        from safeground.env import load_local_env

        load_local_env(env_path)
    except ImportError:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _api_key():
    f = os.path.join(os.path.dirname(__file__), ".cwkey")
    if os.path.exists(f):
        k = open(f).read().strip()
        if k:
            return k
    _load_repo_env()
    return os.environ.get("CYBERWAVE_API_KEY")

MODEL = "google/models/gemini-robotics-er-16"
PROMPT = ("Detect each soda can in the image. For each can, set the label to its "
          "dominant color, exactly one of: green, orange, black.")
LABEL_RISK = {"green": ("SAFE", (90, 210, 90)),
              "orange": ("DANGER", (40, 160, 240)),
              "black": ("AVOID", (200, 170, 110))}
_ml = None
LAST = {}        # metadati REALI dell'ultima run hostata (exec id, formato) — per il monitor back-end

def _client():
    global _ml
    if _ml is None:
        _ml = Cyberwave(api_key=_api_key()).mlmodels
    return _ml

def classify(frame_bgr):
    """frame BGR -> detections [{class,risk,confidence,bbox,center,_px,_col}] (VLM hostato)."""
    h, w = frame_bgr.shape[:2]
    ok, buf = cv2.imencode(".jpg", frame_bgr)
    b64 = base64.b64encode(buf).decode()
    res = _client().run(MODEL, image_base64=b64, structured_task="detect_boxes", prompt=PROMPT)
    LAST.clear(); LAST.update({"uuid": getattr(res, "execution_uuid", None),
                               "fmt": getattr(res, "output_format", None),
                               "status": getattr(res, "status", None)})
    dets = []
    for o in (getattr(res, "output", None) or []):
        box = o.get("box_2d"); lab = (o.get("label") or "").lower()
        rc = next((v for k, v in LABEL_RISK.items() if k in lab), None)
        if not box or rc is None:
            continue
        risk, col = rc
        ymin, xmin, ymax, xmax = [c / 1000.0 for c in box]   # detect_boxes: /1000
        x, y = int(xmin*w), int(ymin*h); bw, bh = int((xmax-xmin)*w), int((ymax-ymin)*h)
        dets.append({"class": lab.split()[0], "risk": risk, "confidence": 0.99,
                     "bbox": [round(xmin, 3), round(ymin, 3), round(xmax-xmin, 3), round(ymax-ymin, 3)],
                     "center": (x + bw//2, y + bh//2), "_px": (x, y, bw, bh), "_col": col})
    LAST["n"] = len(dets)
    return dets

if __name__ == "__main__":
    import sys, json
    img = cv2.imread(sys.argv[1])
    print(json.dumps([{k: v for k, v in d.items() if not k.startswith("_")} for d in classify(img)],
                     ensure_ascii=False, indent=1))
