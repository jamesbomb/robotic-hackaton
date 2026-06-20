# live_vision — strumento live di percezione (SENSE)

Tool da laptop per il loop **sense** di SafeGround, con feedback visivo in tempo reale.
Pensato per sviluppo/demo: la stessa logica si innesta sul Go2 cambiando **solo la sorgente del frame**.

## Sorgente del frame
La fonte dell'immagine è un **unico punto configurabile** in cima a `vision.py`:
```python
SOURCE = "camera"   # "camera" (webcam/USB locale) | "go2" (camera del robot via Cyberwave)
CAMERA_INDEX = 0    # indice camera locale; oppure passa --cam N
```
`camera` per sviluppo (qualsiasi webcam/USB; `c` cicla gli indici), `go2` per il frame del robot (`go2.capture_frame`). Nessun device personale hardcoded.

## Cosa fa
- finestra live della sorgente scelta (camera locale o frame del Go2)
- **SENSE definitivo = VLM hostato Cyberwave** (`google/models/gemini-robotics-er-16`, task `detect_boxes`):
  prompt -> box + etichetta colore -> mappa rischio **SAFE / DANGER / AVOID**
- **monitor back-end live**: stato reale della run hostata (modello, exec-id, latenza, countdown) -> niente fase di stallo durante il riconoscimento
- fallback offline: classificatore CV per colore con training few-shot a rettangoli (calibrazione nuance + forma), pannello controlli cliccabile

## Innesto nella pipeline SafeGround
`cv_safeground.py` espone `CyberwaveVLMClient` con la **stessa firma** di `safeground.cv.MockCVClient`
(`async classify(frame, scenario) -> CVClassification`): è un **drop-in nel `cv_client` del MissionRunner**,
nessuna modifica al codice del team. Mappa il colore al loro enum (verde→NOT_MINE, arancio→MINE, nera→UNCERTAIN/second-look),
sceglie il bersaglio **più pericoloso** del frame (bias di sicurezza) e in caso di rete giù degrada a `UNCERTAIN/HUMAN_REVIEW`.
```python
from live_vision.cv_safeground import CyberwaveVLMClient
runner = MissionRunner(config, robot, CyberwaveVLMClient(), event_store, safety)
```
È un **SENSE alternativo**: più robusto sul colore del worker YOLO+HSV (niente taratura, regge vista/luce);
costo = latenza ~3-5s e dipendenza dalla rete. Il team valuta se sostituire o affiancare.

## File
- `cw_vision.py` — classify(frame) via VLM hostato Cyberwave (il SENSE robusto). Riusabile headless.
- `cv_safeground.py` — adapter: il SENSE dietro il contratto `cv_client` di SafeGround.
- `vision.py` — la finestra live + pannello training + monitor back-end (tasto **V** = VLM hostato)
- `hsv_tune.py` — calibratore HSV (fallback colore)
- `discover_robot.py` — dump capability/movimenti reali del twin Go2 (da lanciare in sede)
- `llm_test.py` — test rapido di un modello hostato su un'immagine

## Run
```bash
.venv/bin/pip install -e .
echo "LA_TUA_CYBERWAVE_API_KEY" > .cwkey   # NON committata (gitignore)
.venv/bin/python live_vision/vision.py --cam 1  # poi premi V per il VLM hostato
```

Se lanci il tool dalla cartella `live_vision`, usa invece:

```bash
../.venv/bin/python vision.py --cam 1
```

## Mappa rischio
verde -> SAFE (lascia) · arancione -> DANGER (rimuovi) · nera -> AVOID (instabile, traccia percorso sicuro)

> La API key vive solo in `.cwkey` locale (gitignored). Stessa key del robot.
