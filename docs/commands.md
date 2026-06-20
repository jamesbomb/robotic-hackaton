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

Esegue lo scenario unico del test fisico, senza hardware, rete, credenziali Cyberwave o CV esterna.

La scena demo contiene contemporaneamente lattine sparse nello spazio:

- lattine arancioni: `MINE`;
- lattine nere: `UNCERTAIN` / dubbio, richiedono seconda osservazione;
- lattine verdi: `NOT_MINE`.

```bash
.venv/bin/python -m safeground.cli --scenario FIELD --print-events
```

Output atteso:

- report JSON per il campo unico;
- eventi JSONL stampati su stdout;
- log append-only in `safeground_runs/events.jsonl`;
- frame fixture copiati in `safeground_runs/frames/`.

`--scenario ALL` resta un alias demo e oggi esegue lo stesso scenario `FIELD`:

```bash
.venv/bin/python -m safeground.cli --scenario ALL --print-events
```

## Scenari Diagnostici

Questi fixture servono solo per test mirati del contratto CV e dei fallback. Non rappresentano il setup fisico principale, che resta `FIELD`.

```bash
.venv/bin/python -m safeground.cli --scenario FIELD
.venv/bin/python -m safeground.cli --scenario MINE
.venv/bin/python -m safeground.cli --scenario NOT_MINE
.venv/bin/python -m safeground.cli --scenario UNCERTAIN
.venv/bin/python -m safeground.cli --scenario INVALID
.venv/bin/python -m safeground.cli --scenario LOW_CONFIDENCE
.venv/bin/python -m safeground.cli --scenario MISSING_BBOX
```

Uso consigliato:

- `FIELD`: scenario unico con lattine arancioni, nere e verdi tutte presenti.
- `MINE`: verifica che il sistema blocchi ogni contatto.
- `NOT_MINE`: verifica il percorso safe-to-contact digitale.
- `UNCERTAIN`: verifica richiesta di second view/human review.
- `INVALID`: verifica fallback sicuro su JSON CV non valido.
- `LOW_CONFIDENCE`: verifica normalizzazione a `UNCERTAIN`.
- `MISSING_BBOX`: verifica gestione target senza bounding box.

## Stampare Eventi

Aggiungere `--print-events` per vedere la timeline completa:

```bash
.venv/bin/python -m safeground.cli --scenario FIELD --print-events
```

## Safe Route E Seconda Verifica

Ogni missione mock registra la traccia seguita dal robot primario come `route_trace` nel report e come evento `ROUTE_RECORDED` nel log.

Nel campo unico `FIELD`, la lattina nera produce il caso `UNCERTAIN`; il robot di verifica usa la route se e' ancora `SAFE`:

```bash
.venv/bin/python -m safeground.cli \
  --command "ispeziona il campo con lattine arancioni nere e verdi" \
  --print-events
```

Eventi attesi:

- `ROUTE_RECORDED`;
- `ROUTE_REUSED_FOR_VERIFICATION`;
- `CONSENSUS_REACHED`.

Per simulare il caso in cui un robot mobile passa sopra una mina, usare:

```bash
.venv/bin/python -m safeground.cli \
  --scenario MINE \
  --route-over-mine \
  --print-events
```

In questo caso la route viene marcata `UNSAFE`, svuotata da `reusable_by`, ed emette `ROUTE_INVALIDATED`. L'eccezione SO-101 e' modellata: il braccio non invalida una route di locomozione per passaggio sopra mina.

## Log Eventi Dedicato

Per non appendere al log standard:

```bash
.venv/bin/python -m safeground.cli \
  --scenario FIELD \
  --event-log /tmp/safeground-demo-events.jsonl \
  --print-events
```

## Preparazione Funzionalita' Complete

Da fare prima di mostrare la Web UI o una demo integrata:

```bash
.venv/bin/pip install -e .
cd frontend
npm install
cd ..
.venv/bin/python -m unittest discover -s tests
cd frontend
npm run build
cd ..
```

Questa sequenza prepara insieme:

- backend FastAPI e dipendenze Python;
- frontend Vue/Vite e lockfile npm;
- agenti mock per Go2, UGV Beast, SO-101 e camera fissa;
- scenario `FIELD` con lattine arancioni, nere e verdi;
- controlli Web UI per start/stop, command palette, movement bounded e SO-101 manual takeover;
- test automatici e build frontend.

## Avvio Web UI

Terminale 1, backend FastAPI:

```bash
.venv/bin/uvicorn safeground.api.server:app --reload
```

Terminale 2, frontend Vue/Vite:

```bash
cd frontend
npm run dev
```

Aprire:

```text
http://localhost:5173
```

Flusso Web UI consigliato:

1. Verificare banner `mock` e `DRY RUN`.
2. Premere `Start Field Scan`.
3. Controllare che timeline e pannelli mostrino Go2, UGV Beast, SO-101 e camera fissa.
4. Verificare `ROUTE_RECORDED`, `ROUTE_REUSED_FOR_VERIFICATION` e `CONSENSUS_REACHED`.
5. Usare `Command Palette` con: `ispeziona il campo con lattine arancioni nere e verdi`.
6. Premere `Stop All` per dimostrare override umano.
7. Usare i pannelli manuali solo in dry-run: micro-movimento bounded e SO-101 takeover.

## Comandi Chat

I comandi chat vengono interpretati in intenti strutturati prima di raggiungere la mission state machine.

```bash
.venv/bin/python -m safeground.cli --command "ispeziona il campo con lattine arancioni nere e verdi"
```

Esempio con scenario unico esplicito:

```bash
.venv/bin/python -m safeground.cli \
  --command "ispeziona il campo completo" \
  --scenario FIELD \
  --print-events
```

Esempi diagnostici utili:

```bash
.venv/bin/python -m safeground.cli --command "ispeziona il campo con lattine"
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

2. Eseguire demo mock completa sul campo unico:

```bash
.venv/bin/python -m safeground.cli --scenario FIELD --print-events
```

3. Avviare backend Web UI:

```bash
.venv/bin/uvicorn safeground.api.server:app --reload
```

4. Avviare frontend Web UI in un secondo terminale:

```bash
cd frontend
npm run dev
```

5. Dalla Web UI premere `Start Field Scan`, poi mostrare command palette o CLI:

```bash
.venv/bin/python -m safeground.cli --command "ispeziona il campo con lattine arancioni nere e verdi" --print-events
```

6. Mostrare stop diretto:

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
- Le route primarie sono riusabili dai robot di verifica solo se restano `SAFE`.
- Una route viene invalidata se un robot mobile, escluso SO-101, passa sopra una mina confermata.

## Troubleshooting

### `ModuleNotFoundError`

Assicurarsi di eseguire dalla root e con `.venv/bin/python`:

```bash
cd /Users/angry/personal/hackaton
.venv/bin/python -m safeground.cli --scenario FIELD
```

### Whisper non installato

Installare solo se serve input vocale:

```bash
.venv/bin/pip install openai-whisper
```

### Log troppo lungo

Usare un log temporaneo:

```bash
.venv/bin/python -m safeground.cli --scenario FIELD --event-log /tmp/safeground-events.jsonl
```

### Pulizia artefatti demo

Gli artefatti sono ignorati da git e possono essere rimossi:

```bash
rm -rf safeground_runs/
```
