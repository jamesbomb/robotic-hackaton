#!/usr/bin/env python3
"""
hsv_tune.py — il calibratore HSV (5 minuti, separa "funziona" da "funziona ALLA DEMO").

Apre la webcam. CLIC su una lattina → stampa+overlay i valori HSV di quel pixel.
Trackbar per impostare un range e vedere la MASCHERA live. 'p' = stampa i range
attuali (copia-incolla in vision.py). Tasti 1/2/3 = preset verde/arancione/nera.

Lattine colorate = proxy mine:
  VERDE    = sicura  → lasciare
  ARANCIONE= rimovibile → braccio
  NERA     = pericolo → V basso (V<60), NON per hue. Occhio ai riflessi sulla lattina lucida.

Uso:  python hsv_tune.py            # webcam 0
      python hsv_tune.py --cam 1    # altra camera
"""
import cv2, numpy as np, sys

CAM = 0
if "--cam" in sys.argv:
    CAM = int(sys.argv[sys.argv.index("--cam") + 1])

# preset iniziali (verranno tarati SUL POSTO con la luce della sala)
PRESETS = {
    "verde":     ([35, 80, 60], [85, 255, 255]),
    "arancione": ([5, 120, 120], [25, 255, 255]),
    "nera":      ([0, 0, 0], [180, 255, 60]),   # NERA = Value basso, qualunque hue
}
order = ["verde", "arancione", "nera"]
cur = 0

last_hsv = None
def on_mouse(ev, x, y, flags, param):
    global last_hsv
    if ev == cv2.EVENT_LBUTTONDOWN and param is not None:
        last_hsv = param[y, x].tolist()
        print(f"[clic] HSV = {last_hsv}  (classe corrente: {order[cur]})")

cv2.namedWindow("tune")
cv2.setMouseCallback("tune", on_mouse)
def nop(v): pass
for i, ch in enumerate("HSV"):
    cv2.createTrackbar(f"{ch}min", "tune", PRESETS[order[cur]][0][i], 255 if ch != "H" else 180, nop)
    cv2.createTrackbar(f"{ch}max", "tune", PRESETS[order[cur]][1][i], 255 if ch != "H" else 180, nop)

def set_trackbars(name):
    lo, hi = PRESETS[name]
    for i, ch in enumerate("HSV"):
        cv2.setTrackbarPos(f"{ch}min", "tune", lo[i])
        cv2.setTrackbarPos(f"{ch}max", "tune", hi[i])

cap = cv2.VideoCapture(CAM)
if not cap.isOpened():
    print(f"ERRORE: webcam {CAM} non si apre. Prova --cam 1.", file=sys.stderr); sys.exit(1)
print("clic su una lattina = leggi HSV · trackbar = range · 1/2/3 = verde/arancione/nera · p = stampa range · q = esci")

while True:
    ok, frame = cap.read()
    if not ok: break
    frame = cv2.resize(frame, (960, 540))
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    cv2.setMouseCallback("tune", on_mouse, hsv)
    lo = np.array([cv2.getTrackbarPos(f"{c}min", "tune") for c in "HSV"])
    hi = np.array([cv2.getTrackbarPos(f"{c}max", "tune") for c in "HSV"])
    mask = cv2.inRange(hsv, lo, hi)
    mask3 = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
    view = np.hstack([frame, cv2.bitwise_and(frame, mask3)])
    cv2.putText(view, f"classe: {order[cur]}  range lo={lo.tolist()} hi={hi.tolist()}",
                (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    if last_hsv:
        cv2.putText(view, f"ultimo clic HSV={last_hsv}", (10, 52),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    cv2.imshow("tune", view)
    k = cv2.waitKey(1) & 0xFF
    if k == ord("q"): break
    elif k in (ord("1"), ord("2"), ord("3")):
        cur = k - ord("1"); set_trackbars(order[cur]); print(f"→ preset {order[cur]}")
    elif k == ord("p"):
        print(f'    "{order[cur]}": ({lo.tolist()}, {hi.tolist()}),')

cap.release(); cv2.destroyAllWindows()
