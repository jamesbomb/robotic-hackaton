#!/usr/bin/env python3
"""
llm_test.py — prova moondream (Ollama, LOCALE, zero API key) su un'immagine.
Verifica empirica: il VLM vede le 3 lattine e le classifica senza taratura colore?

Uso:  python llm_test.py <immagine.jpg>
"""
import sys, json, base64, urllib.request

IMG = sys.argv[1] if len(sys.argv) > 1 else None
MODEL = sys.argv[2] if len(sys.argv) > 2 else "moondream"
if not IMG:
    print("uso: python llm_test.py <immagine> [modello]"); sys.exit(1)

b64 = base64.b64encode(open(IMG, "rb").read()).decode()
prompt = (
    "Questa scena ha delle lattine di bibita su un tavolo. "
    "Per ogni lattina dimmi il COLORE DOMINANTE (verde, arancione, o nera) e dove si trova "
    "(sinistra/centro/destra). Sii conciso, una riga per lattina."
)
req = urllib.request.Request(
    "http://localhost:11434/api/generate",
    data=json.dumps({"model": MODEL, "prompt": prompt, "images": [b64], "stream": False}).encode(),
    headers={"Content-Type": "application/json"},
)
import time
t0 = time.time()
with urllib.request.urlopen(req, timeout=180) as r:
    out = json.loads(r.read())
print(f"[{MODEL}] {time.time()-t0:.1f}s\n")
print(out.get("response", out))
