# SafeGround Commands

Comandi operativi per il prototipo SafeGround P0.

Tutti i comandi vanno eseguiti dalla root del repository:

```bash
cd /Users/angry/personal/hackaton
```

Usare sempre il virtualenv del progetto:

```bash
.venv/bin/python ...
```

## Verifica Ambiente

```bash
.venv/bin/python --version
.venv/bin/python -c "from cyberwave import Cyberwave; print('Cyberwave SDK OK')"
```

## Demo Mock Completa

Esegue i tre scenari principali (`NOT_MINE`, `MINE`, `UNCERTAIN`) senza hardware, rete, credenziali Cyberwave o CV esterna.

```bash
.venv/bin/python -m safeground.cli --scenario ALL --print-events
```

Output atteso:

- report JSON per ogni scenario;
- eventi JSONL stampati su stdout;
- log append-only in `safeground_runs/events.jsonl`;
- frame fixture copiati in `safeground_runs/frames/`.

## Scenari Singoli

```bash
.venv/bin/python -m safeground.cli --scenario MINE
.venv/bin/python -m safeground.cli --scenario NOT_MINE
.venv/bin/python -m safeground.cli --scenario UNCERTAIN
.venv/bin/python -m safeground.cli --scenario INVALID
.venv/bin/python -m safeground.cli --scenario LOW_CONFIDENCE
.venv/bin/python -m safeground.cli --scenario MISSING_BBOX
```

Uso consigliato:

- `MINE`: verifica che il sistema blocchi ogni contatto.
- `NOT_MINE`: verifica il percorso safe-to-contact digitale.
- `UNCERTAIN`: verifica richiesta di second view/human review.
- `INVALID`: verifica fallback sicuro su JSON CV non valido.
- `LOW_CONFIDENCE`: verifica normalizzazione a `UNCERTAIN`.
- `MISSING_BBOX`: verifica gestione target senza bounding box.

## Stampare Eventi

Aggiungere `--print-events` per vedere la timeline completa:

```bash
.venv/bin/python -m safeground.cli --scenario UNCERTAIN --print-events
```

## Log Eventi Dedicato

Per non appendere al log standard:

```bash
.venv/bin/python -m safeground.cli \
  --scenario MINE \
  --event-log /tmp/safeground-demo-events.jsonl \
  --print-events
```

## Comandi Chat

I comandi chat vengono interpretati in intenti strutturati prima di raggiungere la mission state machine.

```bash
.venv/bin/python -m safeground.cli --command "ispeziona settore B2"
```

Esempio con scenario suggerito nel testo:

```bash
.venv/bin/python -m safeground.cli \
  --command "ispeziona settore B2 con scenario dubbio" \
  --print-events
```

Esempi utili:

```bash
.venv/bin/python -m safeground.cli --command "ispeziona settore A1 con scenario mine"
.venv/bin/python -m safeground.cli --command "ispeziona settore B2 con scenario non mine"
.venv/bin/python -m safeground.cli --command "ispeziona settore C3 con scenario dubbio"
.venv/bin/python -m safeground.cli --command "mostra status"
```

## Stop Diretto

I comandi di stop bypassano la pianificazione e vanno direttamente al percorso deterministico di stop.

```bash
.venv/bin/python -m safeground.cli --command "ferma tutto" --print-events
.venv/bin/python -m safeground.cli --command "stop"
.venv/bin/python -m safeground.cli --command "halt"
```

Output atteso:

- stato missione `MANUAL_STOP`;
- evento `MISSION_STOPPED`;
- nessun frame capture;
- nessuna classificazione.

## Comandi Fuori Scope

Comandi non riconosciuti non muovono hardware e richiedono revisione umana.

```bash
.venv/bin/python -m safeground.cli --command "raccontami una barzelletta" --print-events
```

Output atteso:

- nessuna missione avviata;
- summary con human review;
- eventi `USER_COMMAND_RECEIVED`, `AGENT_INTENT_PARSED`, `AGENT_DECISION_MADE`.

## Voce Con Whisper

La voce e' secondaria. Whisper trascrive un file audio, poi il testo segue lo stesso percorso dei comandi chat.

Installazione opzionale:

```bash
.venv/bin/pip install openai-whisper
```

Esecuzione:

```bash
.venv/bin/python -m safeground.cli \
  --voice-wav input.wav \
  --whisper-model tiny \
  --print-events
```

Note:

- `--voice-wav` richiede un file audio esistente.
- `--whisper-model` default: `tiny`.
- Se `openai-whisper` non e' installato, il comando fallisce con istruzioni esplicite.
- La voce non decide azioni robotiche: produce solo testo da passare al path chat.

## Test

```bash
.venv/bin/python -m unittest discover -s tests
```

Risultato atteso:

```text
OK
```

## Sequenza Demo Consigliata

1. Verificare test:

```bash
.venv/bin/python -m unittest discover -s tests
```

2. Eseguire demo mock completa:

```bash
.venv/bin/python -m safeground.cli --scenario ALL --print-events
```

3. Mostrare comando chat:

```bash
.venv/bin/python -m safeground.cli --command "ispeziona settore B2 con scenario dubbio" --print-events
```

4. Mostrare stop diretto:

```bash
.venv/bin/python -m safeground.cli --command "ferma tutto" --print-events
```

## Sicurezza

- Il prototipo parte in mock/dry-run.
- Nessun comando chat o voce invia comandi motore raw.
- Gli agenti producono intenti e decisioni strutturate.
- Il `SafetyGovernor` applica allow-list e timeout prima degli adapter.
- Stop testuale/vocale deve restare il percorso piu' diretto possibile.
- Oggetti `MINE` o `UNCERTAIN` non devono essere toccati.

## Troubleshooting

### `ModuleNotFoundError`

Assicurarsi di eseguire dalla root e con `.venv/bin/python`:

```bash
cd /Users/angry/personal/hackaton
.venv/bin/python -m safeground.cli --scenario MINE
```

### Whisper non installato

Installare solo se serve input vocale:

```bash
.venv/bin/pip install openai-whisper
```

### Log troppo lungo

Usare un log temporaneo:

```bash
.venv/bin/python -m safeground.cli --scenario ALL --event-log /tmp/safeground-events.jsonl
```

### Pulizia artefatti demo

Gli artefatti sono ignorati da git e possono essere rimossi:

```bash
rm -rf safeground_runs/
```
