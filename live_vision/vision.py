#!/usr/bin/env python3
"""
vision.py — SENSE: vede le 3 lattine e le classifica per NUANCE ESATTA + confidence.

Niente range fissi (non transferano). CALIBRI la nuance vera di ogni lattina con un
click; poi la confidence = quanto un blob e' vicino a quella nuance (0-100%).

  verde     -> SAFE   (lascia)
  arancione -> DANGER (rimuovi)
  nera      -> AVOID  (instabile -> traccia/mappa percorso sicuro)

CALIBRAZIONE:  premi  k  -> clicca sul VERDE, poi ARANCIONE, poi NERA. Salvato in calib.json.
Tasti:  k=calibra - c=camera - d=dev - s=salva - q=esci
Uso:    .venv/bin/python vision.py        (poi premi k e calibra sulle tue lattine)
"""
import cv2, numpy as np, sys, time, json, os, threading

FONT = cv2.FONT_HERSHEY_DUPLEX      # meno "Doom" del SIMPLEX
INK = (236, 231, 223)
def shade(frame, x0, y0, x1, y1, alpha=0.62, col=(14, 15, 19)):
    """barra semi-trasparente (look moderno invece del rettangolo pieno)."""
    sub = frame[max(0,y0):y1, max(0,x0):x1]
    if sub.size: sub[:] = (sub * (1-alpha) + np.array(col) * alpha).astype(np.uint8)
CALIB_FILE = os.path.join(os.path.dirname(__file__), "calib.json")

CLASSES = {  # ordine di calibrazione = ordine qui
    "verde":     {"risk": "SAFE",   "col": (90, 210, 90)},
    "arancione": {"risk": "DANGER", "col": (40, 160, 240)},
    "nera":      {"risk": "AVOID",  "col": (200, 160, 90)},
}
# tolleranza AUTO per-lattina: derivata dalla dispersione del campione (ogni colore la sua)
TOL_MIN = np.array([6, 25, 25]); TOL_MAX = np.array([22, 110, 120]); TOL_K = 2.5
MAXD = 60.0                    # distanza-colore a cui la confidence-colore va a 0
AREA_MIN_FRAC, AREA_MAX_FRAC = 0.0004, 0.090   # min basso: lattine lontane = piccole
ASPECT_MIN, ASPECT_MAX = 0.2, 2.6              # largo: il punto di vista cambia la forma
SOLIDITY_MIN = 0.70
DEV = False               # griglia debug OFF di default (tasto d per accenderla)

CAL = {}                       # class -> {"t":[H,S,V] nuance, "tol":[H,S,V] tolleranza auto}
if os.path.exists(CALIB_FILE):
    try: CAL = {k: {"t": np.array(v["t"]), "tol": np.array(v["tol"]), "aspect": v.get("aspect")} for k, v in json.load(open(CALIB_FILE)).items()}
    except Exception: CAL = {}

def text(img, s, org, scale=0.6, color=INK, thick=2):
    cv2.putText(img, s, org, FONT, scale, (0, 0, 0), thick + 3, cv2.LINE_AA)
    cv2.putText(img, s, org, FONT, scale, color, thick, cv2.LINE_AA)

def hue_dist(a, b):
    d = abs(float(a) - float(b)); return min(d, 180 - d)

def color_distance(mean_hsv, target):
    dh = hue_dist(mean_hsv[0], target[0]) * 2.0      # hue pesa di piu' (identita' colore)
    ds = abs(float(mean_hsv[1]) - float(target[1])) * 0.5
    dv = abs(float(mean_hsv[2]) - float(target[2])) * 0.6
    return (dh*dh + ds*ds + dv*dv) ** 0.5

def classify(frame_bgr):
    h, w = frame_bgr.shape[:2]
    area_min, area_max = AREA_MIN_FRAC*h*w, AREA_MAX_FRAC*h*w
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    dets = []
    for name, cfg in CLASSES.items():
        if name not in CAL:                          # non calibrato -> salta
            continue
        t, tol = CAL[name]["t"], CAL[name]["tol"]
        lo = np.clip(t - tol, [0, 0, 0], [179, 255, 255]).astype(np.uint8)
        hi = np.clip(t + tol, [0, 0, 0], [179, 255, 255]).astype(np.uint8)
        mask = cv2.inRange(hsv, lo, hi)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in cnts:
            area = cv2.contourArea(c)
            if not (area_min < area < area_max):              # F1 size
                continue
            x, y, bw, bh = cv2.boundingRect(c)
            ar = bw / max(bh, 1)
            if not (ASPECT_MIN < ar < ASPECT_MAX):    # F2 forma: solo sanity larga (il viewpoint cambia l'aspect)
                continue
            solidity = area / max(cv2.contourArea(cv2.convexHull(c)), 1)
            if solidity < SOLIDITY_MIN:                       # F3 solidita'
                continue
            blob = np.zeros((h, w), np.uint8); cv2.drawContours(blob, [c], -1, 255, -1)
            mean = cv2.mean(hsv, mask=blob)[:3]
            color_conf = max(0.0, 1.0 - color_distance(mean, t) / MAXD)   # NUANCE 0-100%
            fill = area / max(bw * bh, 1)
            conf = round(float(min(1.0, 0.55*color_conf + 0.25*solidity + 0.20*fill)), 2)
            dets.append({"class": name, "risk": cfg["risk"], "confidence": conf,
                         "bbox": [round(x/w, 3), round(y/h, 3), round(bw/w, 3), round(bh/h, 3)],
                         "center": (x + bw//2, y + bh//2), "_px": (x, y, bw, bh), "_col": cfg["col"]})
    dets.sort(key=lambda d: -d["confidence"])         # dedup sovrapposti
    keep = []
    for d in dets:
        if all(_iou(d["_px"], k["_px"]) < 0.4 for k in keep):
            keep.append(d)
    return keep

def _iou(a, b):
    ax, ay, aw, ah = a; bx, by, bw, bh = b
    x1, y1 = max(ax, bx), max(ay, by); x2, y2 = min(ax+aw, bx+bw), min(ay+ah, by+bh)
    inter = max(0, x2-x1) * max(0, y2-y1)
    return inter / max(aw*ah + bw*bh - inter, 1)

def draw_dev(frame):
    h, w = frame.shape[:2]; grid = (60, 64, 72)
    for f in range(1, 10):
        cv2.line(frame, (int(w*f/10), 32), (int(w*f/10), h), grid, 1, cv2.LINE_AA)
        cv2.line(frame, (0, int(h*f/10)), (w, int(h*f/10)), grid, 1, cv2.LINE_AA)
    cv2.drawMarker(frame, (w//2, h//2), (150, 190, 230), cv2.MARKER_CROSS, 26, 1, cv2.LINE_AA)

# ── REASON: rischio -> azione + mappa-rischio che si popola ───────────────
ACTION_OF = {"SAFE": "LASCIA", "DANGER": "RIMUOVI", "AVOID": "EVITA+TRACCIA"}
GRID_COLS, GRID_ROWS = 9, 6
RISK_RANK = {"SAFE": 1, "AVOID": 2, "DANGER": 3}    # tieni il piu' pericoloso per cella
RISK_COL = {"SAFE": (90, 210, 90), "DANGER": (60, 60, 230), "AVOID": (200, 170, 110)}
MAP = {}                                            # (col,row) -> risk (memoria del cane)

def update_map(dets, w, h):
    for d in dets:
        cx, cy = d["center"]
        c = min(GRID_COLS-1, max(0, int(cx / w * GRID_COLS)))
        r = min(GRID_ROWS-1, max(0, int(cy / h * GRID_ROWS)))
        cur = MAP.get((c, r))
        if cur is None or RISK_RANK[d["risk"]] > RISK_RANK[cur]:
            MAP[(c, r)] = d["risk"]

def draw_minimap(frame):
    h, w = frame.shape[:2]
    mw, mh = 198, 126; x0, y0 = 12, h - mh - 46
    shade(frame, x0 - 6, y0 - 24, x0 + mw + 8, y0 + mh + 8, alpha=0.6)
    text(frame, "MAPPA RISCHIO", (x0, y0 - 7), 0.45, INK, 1)
    cwc, chc = mw // GRID_COLS, mh // GRID_ROWS
    for c in range(GRID_COLS):
        for r in range(GRID_ROWS):
            x, y = x0 + c*cwc, y0 + r*chc
            risk = MAP.get((c, r))
            if risk: cv2.rectangle(frame, (x, y), (x+cwc-1, y+chc-1), RISK_COL[risk], -1)
            cv2.rectangle(frame, (x, y), (x+cwc-1, y+chc-1), (60, 64, 72), 1)

def draw(frame, dets):
    h, w = frame.shape[:2]; counts = {"SAFE": 0, "DANGER": 0, "AVOID": 0}
    for d in dets:
        x, y, bw, bh = d["_px"]; col = d["_col"]; counts[d["risk"]] += 1
        cx, cy = d["center"]
        cv2.rectangle(frame, (x, y), (x + bw, y + bh), col, 2, cv2.LINE_AA)
        cv2.circle(frame, (cx, cy), 4, col, -1, cv2.LINE_AA)
        ly = y - 10 if y > 50 else y + bh + 22
        text(frame, f'{d["risk"]} {int(d["confidence"]*100)}%  ->  {ACTION_OF[d["risk"]]}', (x, ly), 0.55, col, 2)
        cv2.rectangle(frame, (x, ly + 4), (x + int(bw * d["confidence"]), ly + 8), col, -1)
    return counts

def hud(frame, counts, cam_idx, fps, calmsg):
    w = frame.shape[1]
    shade(frame, 0, 0, w, 34)
    text(frame, f"SAFE {counts['SAFE']}", (12, 22), 0.6, (110, 220, 110), 2)
    text(frame, f"DANGER {counts['DANGER']}", (130, 22), 0.6, (90, 180, 250), 2)
    text(frame, f"AVOID {counts['AVOID']}", (320, 22), 0.6, (200, 170, 110), 2)
    msg = calmsg or f"cam {cam_idx}  {fps:4.1f}fps   (comandi nel pannello a destra)"
    text(frame, msg, (max(470, w-560), 22), 0.5, (255, 230, 120) if calmsg else (150, 155, 165), 1 if not calmsg else 2)

# ── stato calibrazione (mouse) ───────────────────────────────────────────
CAL_QUEUE = list(CLASSES.keys())          # [verde, arancione, nera]
RISK_OF = {n: CLASSES[n]["risk"] for n in CAL_QUEUE}
LATEST_HSV = None
DRAG = None                               # [x0,y0,x1,y1] rettangolo in trascinamento
TRAIN = False                             # modalita' training attiva
ACTIVE = 0                                # classe attiva (indice in CAL_QUEUE)
SAMPLES = {n: [] for n in CAL_QUEUE}      # few-shot: n -> lista di campioni {t,sp,ar}

WCAM, WPANEL = 960, 300        # video + pannello controlli cliccabile

def on_mouse(ev, x, y, flags, param):
    global DRAG, ACTIVE, TRAIN, VLM_ON
    if x >= WCAM:                              # --- PANNELLO: bottoni cliccabili ---
        if ev == cv2.EVENT_LBUTTONDOWN:
            hit = panel_hit(x - WCAM, y)
            if hit:
                kind, val = hit
                if kind == "class": ACTIVE = val; TRAIN = True
                elif kind == "train":
                    TRAIN = not TRAIN
                    if not TRAIN and CAL: save_calib()
                elif kind == "clear":
                    SAMPLES[CAL_QUEUE[ACTIVE]].clear(); CAL.pop(CAL_QUEUE[ACTIVE], None)
                elif kind == "save": save_calib()
                elif kind == "vlm": VLM_ON = not VLM_ON
        return
    if ev == cv2.EVENT_LBUTTONDOWN:            # --- VIDEO: trascina un box = campione ---
        DRAG = [x, y, x, y]
    elif ev == cv2.EVENT_MOUSEMOVE and DRAG is not None:
        DRAG[2], DRAG[3] = x, y
    elif ev == cv2.EVENT_LBUTTONUP and DRAG is not None:
        box = DRAG; DRAG = None
        if TRAIN and LATEST_HSV is not None:
            add_sample(*box)

DCOL_RISK = {"SAFE": (110, 220, 110), "DANGER": (90, 180, 250), "AVOID": (200, 170, 110)}
def panel_hit(px, py):
    for i in range(len(CAL_QUEUE)):
        y = 64 + i*42
        if 14 <= px <= WPANEL-14 and y <= py <= y+34: return ("class", i)
    if 200 <= py <= 234: return ("train", None)
    if 250 <= py <= 284: return ("clear", None)
    if 292 <= py <= 326: return ("save", None)
    if 336 <= py <= 372: return ("vlm", None)
    return None

def draw_panel(h):
    p = np.full((h, WPANEL, 3), 24, np.uint8)
    text(p, "TRAINING", (16, 36), 0.7, INK, 2)
    for i, n in enumerate(CAL_QUEUE):
        on = (i == ACTIVE and TRAIN); y = 64 + i*42; rc = DCOL_RISK[RISK_OF[n]]
        cv2.rectangle(p, (14, y), (WPANEL-14, y+34), rc if on else (44, 46, 52), -1)
        cv2.rectangle(p, (14, y), (WPANEL-14, y+34), (230, 230, 230) if on else (70, 74, 82), 1)
        text(p, f"{i+1}  {RISK_OF[n]}", (26, y+23), 0.6, (10, 10, 10) if on else INK, 2)
        text(p, f"{len(SAMPLES[n])} es.", (WPANEL-90, y+23), 0.5, (10, 10, 10) if on else (165, 170, 180), 1)
    def btn(y, label, col=(50, 53, 60), tc=INK, th=1):
        cv2.rectangle(p, (14, y), (WPANEL-14, y+34), col, -1)
        cv2.rectangle(p, (14, y), (WPANEL-14, y+34), (90, 94, 102), 1)
        text(p, label, (26, y+23), 0.55, tc, th)
    btn(200, f"TRAIN: {'ON' if TRAIN else 'OFF'}   [T]", tc=(120, 220, 120) if TRAIN else (200, 170, 110), th=2)
    btn(250, "SVUOTA classe   [X]")
    btn(292, "SALVA e classifica   [S]", tc=(120, 220, 120), th=2)
    btn(336, f"VLM Cyberwave: {'ON' if VLM_ON else 'OFF'}   [V]",
        col=(36, 60, 44) if VLM_ON else (50, 53, 60),
        tc=(120, 230, 140) if VLM_ON else (200, 170, 110), th=2)
    if VLM_ON:
        st = {"analyzing": "analizzo…", "done": f"ok {VLM_LAST.get('n',0)} oggetti",
              "error": "errore", "idle": "pronto"}.get(VLM_STATE, VLM_STATE)
        text(p, f"  hostato - {st}", (20, 392), 0.42, (150, 200, 160), 1)
    text(p, "CV training [1/2/3 T X S] - VLM [V]", (16, 416), 0.42, (160, 165, 175), 1)
    text(p, "campione: trascina box - c=cam q=esci", (16, 436), 0.42, (160, 165, 175), 1)
    return p

def add_sample(x0, y0, x1, y1):
    """un rettangolo = un CAMPIONE della classe attiva (colore+forma)."""
    H, W = LATEST_HSV.shape[:2]
    ax0, ay0 = max(0, min(x0, x1)), max(0, min(y0, y1))
    ax1, ay1 = min(W, max(x0, x1)), min(H, max(y0, y1))
    if ax1 - ax0 < 6 or ay1 - ay0 < 6:
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        ax0, ay0, ax1, ay1 = max(0, cx-12), max(0, cy-12), min(W, cx+12), min(H, cy+12)
    patch = LATEST_HSV[ay0:ay1, ax0:ax1].reshape(-1, 3).astype(float)
    if len(patch) == 0: return
    name = CAL_QUEUE[ACTIVE]
    SAMPLES[name].append({"t": np.median(patch, axis=0), "sp": np.std(patch, axis=0),
                          "ar": (ax1 - ax0) / max(ay1 - ay0, 1)})
    rebuild(name)
    print(f"[train] {name}: {len(SAMPLES[name])} campioni -> nuance {CAL[name]['t'].astype(int).tolist()}")

def rebuild(name):
    """prototipo classe = firma media + tolleranza che copre TUTTI i campioni."""
    S = SAMPLES[name]
    if not S: return
    nus = np.array([s["t"] for s in S])
    within = np.max([s["sp"] for s in S], axis=0)               # spread dentro i box
    between = np.std(nus, axis=0) if len(S) > 1 else np.zeros(3)  # spread tra i box
    CAL[name] = {"t": np.median(nus, axis=0),
                 "tol": np.clip(TOL_K * within + 1.5 * between, TOL_MIN, TOL_MAX),
                 "aspect": round(float(np.mean([s["ar"] for s in S])), 3)}

def save_calib():
    json.dump({k: {"t": v["t"].tolist(), "tol": v["tol"].tolist(), "aspect": v["aspect"]}
               for k, v in CAL.items()}, open(CALIB_FILE, "w"))
    print("[train] salvato calib.json")

# ╔══ SORGENTE DEL FRAME — l'UNICO punto dove scegli da dove arriva l'immagine ══╗
#   "camera" → camera locale (webcam / USB). Indice CAMERA_INDEX (0,1,2…); 'c' cicla.
#   "go2"    → camera del robot Unitree Go2 via Cyberwave (frame dal twin).
# Cambia SOURCE/CAMERA_INDEX qui sotto, oppure passa --cam N da riga di comando.
SOURCE = "camera"
CAMERA_INDEX = 0
# ╚══════════════════════════════════════════════════════════════════════════════╝

def open_cam(idx):
    cap = cv2.VideoCapture(idx); return cap if cap.isOpened() else None

def open_go2():
    """Frame dal robot — stessa firma read() -> (ok, frame_bgr). Lo swap è SOLO questa funzione."""
    from cyberwave import Cyberwave
    cw = Cyberwave(); go2 = cw.twin("unitree/go2"); cw.affect("live")
    class _Go2Src:
        def read(self):
            f = go2.capture_frame("numpy"); return (f is not None, f)
        def release(self): pass
    return _Go2Src()

# ── SENSE HOSTATO: VLM Cyberwave in background + MONITOR back-end (tasto V) ─
VLM_ON = False; VLM_DETS = []; LATEST_FRAME = None
VLM_STATE = "idle"        # idle | sending | analyzing | done | error
VLM_T0 = 0.0              # inizio analisi corrente (per il cronometro live)
VLM_LAST = {}             # {n, sec, uuid} ultima analisi completata
VLM_NEXT = 0.0            # quando parte la prossima
VLM_PERIOD = 5.0          # cadenza minima tra analisi (s) — non martellare l'API / il robot
def vlm_worker():
    import cw_vision
    last = 0.0
    while True:
        if VLM_ON and LATEST_FRAME is not None and (time.time() - last) >= VLM_PERIOD:
            last = time.time()
            globals()["VLM_STATE"] = "analyzing"; globals()["VLM_T0"] = time.time()
            try:
                d = cw_vision.classify(LATEST_FRAME)
                sec = time.time() - VLM_T0
                globals()["VLM_DETS"] = d
                globals()["VLM_LAST"] = {"n": len(d), "sec": sec, "uuid": cw_vision.LAST.get("uuid")}
                globals()["VLM_STATE"] = "done"; globals()["VLM_NEXT"] = time.time() + VLM_PERIOD
                print(f"[vlm] {len(d)} oggetti in {sec:.1f}s - exec {str(cw_vision.LAST.get('uuid'))[:8]}: {[(x['class'],x['risk']) for x in d]}")
            except Exception as e:
                globals()["VLM_STATE"] = "error"; globals()["VLM_LAST"] = {"err": str(e)[:50]}
                print(f"[vlm] ERRORE: {str(e)[:120]}")
        time.sleep(0.2)

def draw_vlm_status(frame):
    """monitor back-end LIVE: niente stallo, vedi il VLM hostato che lavora davvero."""
    if not VLM_ON: return
    h, w = frame.shape[:2]
    shade(frame, 0, h-34, w, h, alpha=0.66)
    cv2.line(frame, (0, h-34), (w, h-34), (70, 120, 170), 1, cv2.LINE_AA)
    if VLM_STATE == "analyzing":
        el = time.time() - VLM_T0
        dots = "." * (1 + int(el*2) % 3)
        text(frame, f"BACK-END  Cyberwave/gemini-robotics-er  ->  analizzo il frame{dots}  {el:4.1f}s",
             (10, h-10), 0.52, (120, 200, 250), 2)
    elif VLM_STATE == "error":
        text(frame, f"BACK-END  errore: {VLM_LAST.get('err','?')}", (10, h-10), 0.52, (230, 120, 120), 2)
    else:
        L = VLM_LAST; nxt = max(0, VLM_NEXT - time.time())
        text(frame, f"BACK-END  ok {L.get('n',0)} oggetti in {L.get('sec',0):.1f}s  -  exec {str(L.get('uuid',''))[:8]}  -  prossima analisi {nxt:.0f}s",
             (10, h-10), 0.5, (140, 210, 160), 1)

def main():
    global LATEST_HSV, TRAIN, ACTIVE
    cam_idx = int(sys.argv[sys.argv.index("--cam") + 1]) if "--cam" in sys.argv else CAMERA_INDEX
    if SOURCE == "go2":
        cap = open_go2(); cam_idx = -1                 # frame dal robot: 'c' disattivo
    else:
        cap = open_cam(cam_idx)
    if cap is None:
        print("camera non apre. Cambia CAMERA_INDEX o passa --cam N. (macOS: Privacy > Fotocamera).", file=sys.stderr); sys.exit(1)
    win = "vision - quello che vede il robot"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win, WCAM + WPANEL, 540)   # finestra = canvas esatto -> niente barra grigia, click 1:1
    cv2.setMouseCallback(win, on_mouse)
    print("V = VLM hostato Cyberwave - k = training CV - 1/2/3 = classe - trascina = campione")
    threading.Thread(target=vlm_worker, daemon=True).start()   # SENSE hostato, idle finche' V off
    t0 = time.time(); fps = 0.0
    while True:
        ok, frame = cap.read()
        if not ok or frame is None: continue
        frame = cv2.resize(frame, (960, 540))
        globals()["LATEST_FRAME"] = frame.copy()               # frame grezzo per il worker VLM
        LATEST_HSV = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        dets = VLM_DETS if VLM_ON else classify(frame)         # VLM hostato robusto  |  CV-colore live
        if DEV: draw_dev(frame)
        counts = draw(frame, dets)
        update_map(dets, frame.shape[1], frame.shape[0])       # REASON: popola la mappa-rischio
        draw_minimap(frame)
        draw_vlm_status(frame)                                 # monitor back-end live (no stallo)
        dt = time.time() - t0; t0 = time.time(); fps = 0.9*fps + 0.1*(1/dt if dt else 0)
        hud(frame, counts, cam_idx, fps, "")
        canvas = np.hstack([frame, draw_panel(frame.shape[0])])    # video + pannello controlli
        if DRAG is not None:
            cv2.rectangle(canvas, (DRAG[0], DRAG[1]), (DRAG[2], DRAG[3]), (255, 230, 120), 2)
        cv2.imshow(win, canvas)
        k = cv2.waitKey(1) & 0xFF
        if k == ord("q"): break
        elif k == ord("v"):                                # VLM hostato on/off
            globals()["VLM_ON"] = not VLM_ON
            print(f"[vlm] {'ON — VLM Cyberwave hostato' if VLM_ON else 'OFF — CV colore'}")
        elif k in (ord("1"), ord("2"), ord("3")):          # scegli classe (accende TRAIN)
            ACTIVE = k - ord("1"); TRAIN = True
            print(f"[train] classe attiva = {RISK_OF[CAL_QUEUE[ACTIVE]]}")
        elif k in (ord("t"), ord(" ")):                    # T / spazio = TRAIN on/off
            TRAIN = not TRAIN
            if not TRAIN and CAL: save_calib()
        elif k == ord("x"):                                # svuota classe attiva
            SAMPLES[CAL_QUEUE[ACTIVE]].clear(); CAL.pop(CAL_QUEUE[ACTIVE], None)
            print(f"[train] svuotata {RISK_OF[CAL_QUEUE[ACTIVE]]}")
        elif k in (ord("s"), 13):                          # S / INVIO = SALVA training
            save_calib()
        elif k == ord("p"):                                # P = foto + json
            ts = int(time.time()); cv2.imwrite(f"/tmp/vision_{ts}.png", frame)
            print(json.dumps({"frame_id": f"cam-{ts}", "detections":
                  [{kk: vv for kk, vv in d.items() if not kk.startswith("_")} for d in dets]}, ensure_ascii=False))
        elif k == ord("m"): MAP.clear(); print("[map] mappa-rischio azzerata")
        elif k == ord("d"): globals()["DEV"] = not DEV
        elif k == ord("c") and cam_idx >= 0:           # cicla camere (solo sorgente locale)
            cap.release()
            for j in range(1, 5):
                c2 = open_cam((cam_idx + j) % 5)
                if c2 is not None: cap, cam_idx = c2, (cam_idx + j) % 5; break
            else: cap = open_cam(cam_idx)
    cap.release(); cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
