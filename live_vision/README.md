# live_vision — strumento live di percezione (SENSE)

Tool da laptop per il loop **sense** di SafeGround, con feedback visivo in tempo reale.
Pensato per sviluppo/demo: poi la stessa logica si innesta sul Go2 (una riga: webcam -> `go2.capture_frame`).

## Cosa fa
- finestra live della camera (webcam/iPhone via Continuity, o domani il frame del Go2)
- **SENSE definitivo = VLM hostato Cyberwave** (`google/models/gemini-robotics-er-16`, task `detect_boxes`):
  prompt -> box + etichetta colore -> mappa rischio **SAFE / DANGER / AVOID**
- **monitor back-end live**: stato reale della run hostata (modello, exec-id, latenza, countdown) -> niente fase di stallo durante il riconoscimento
- fallback offline: classificatore CV per colore con training few-shot a rettangoli (calibrazione nuance + forma), pannello controlli cliccabile

## File
- `cw_vision.py` — classify(frame) via VLM hostato Cyberwave (il SENSE robusto). Riusabile headless.
- `vision.py` — la finestra live + pannello training + monitor back-end (tasto **V** = VLM hostato)
- `hsv_tune.py` — calibratore HSV (fallback colore)
- `discover_robot.py` — dump capability/movimenti reali del twin Go2 (da lanciare in sede)
- `llm_test.py` — test rapido di un modello hostato su un'immagine

## Run
```bash
python -m venv .venv && .venv/bin/pip install opencv-python numpy cyberwave
echo "LA_TUA_CYBERWAVE_API_KEY" > .cwkey   # NON committata (gitignore)
.venv/bin/python vision.py --cam 1          # poi premi V per il VLM hostato
```

## Mappa rischio
verde -> SAFE (lascia) · arancione -> DANGER (rimuovi) · nera -> AVOID (instabile, traccia percorso sicuro)

> La API key vive solo in `.cwkey` locale (gitignored). Stessa key del robot.
