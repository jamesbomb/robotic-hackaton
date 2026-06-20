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

## Live Vision Sense Tool

La PR #1 aggiunge `live_vision/`, un tool laptop additivo per il loop `sense` con webcam o frame robot e VLM Cyberwave hostato.

Preparazione:

```bash
.venv/bin/pip install -e .
echo "LA_TUA_CYBERWAVE_API_KEY" > live_vision/.cwkey
```

Avvio webcam:

```bash
.venv/bin/python live_vision/vision.py --cam 1
```

Comandi principali nella finestra:

- `V`: abilita/disabilita VLM hostato Cyberwave;
- `1/2/3`, `T`, drag box: training fallback colore;
- `S`: salva calibrazione locale;
- `q`: esce.

## Safe Route E Seconda Verifica

Ogni missione mock registra la traccia seguita dal robot primario come `route_trace` nel report e come evento `ROUTE_RECORDED` nel log.

Nel campo unico `FIELD`, la lattina nera produce il caso `UNCERTAIN`; il robot di verifica usa la route se e' ancora `SAFE`:

```bash
.venv/bin/python -m safeground.cli \
  --command "ispeziona il campo in cerca di mine" \
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

La mappa completa dei movimenti disponibili per Go2, UGV Beast e SO-101 e'
in `docs/robot_movement_capability_map.md`.

## Setup Mac Collaboratore

Questa sequenza prepara un Mac pulito per lavorare su SafeGround in mock,
simulation e digital twin. Sostituire `<REPO_URL>` con l'URL reale del repository.

Prerequisiti macOS:

```bash
xcode-select --install
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install python@3.13 node git
```

Clone e installazione progetto:

```bash
git clone <REPO_URL> safeground
cd safeground
python3.13 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -e . cyberwave
cd frontend
npm install
cd ..
```

Verifica locale:

```bash
.venv/bin/python -m unittest discover -s tests
cd frontend
npm run build
cd ..
```

Avvio Web UI in due terminali:

```bash
# Terminale 1
cd safeground
.venv/bin/uvicorn safeground.api.server:app --reload
```

```bash
# Terminale 2
cd safeground/frontend
npm run dev
```

Aprire:

```text
http://localhost:5173
```

### Setup Cyberwave Per Digital Twin

Installare Cyberwave CLI/Edge sul Mac del collaboratore:

```bash
curl -fsSL https://cyberwave.com/install.sh | bash
cyberwave --version
```

Eseguire login/pairing quando richiesto dal setup Cyberwave:

```bash
cyberwave pair
cyberwave edge logs
```

Se il setup Cyberwave produce file locali in `~/.cyberwave`, SafeGround li legge
automaticamente da `~/.cyberwave`. In alternativa, puntare SafeGround a una copia
della configurazione:

```bash
cp .env.example .env 2>/dev/null || touch .env
cat >> .env <<'EOF'
SAFEGROUND_RUNTIME_MODE=simulation
SAFEGROUND_DRY_RUN=true
EOF
```

Se Cyberwave richiede credenziali SDK per leggere frame o sincronizzare pose,
aggiungerle a `.env`:

```bash
cat >> .env <<'EOF'
CYBERWAVE_API_KEY=<api-key>
CYBERWAVE_ENVIRONMENT=<environment-id>
EOF
```

Smoke test discovery e attivazione virtuale:

```bash
curl http://localhost:8000/api/cyberwave/robots
curl -X POST http://localhost:8000/api/robots/go2/activate \
  -H 'Content-Type: application/json' \
  -d '{
    "operator_confirmed": true,
    "activation_mode": "ready",
    "allow_physical": false,
    "reason": "collaborator virtual twin activation"
  }'
```

Se il twin scoperto non corrisponde a `go2`, usare il valore `robot_id` ritornato
da `/api/cyberwave/robots`:

```bash
ROBOT_ID=<robot_id-from-discovery>
curl -X POST "http://localhost:8000/api/robots/${ROBOT_ID}/activate" \
  -H 'Content-Type: application/json' \
  -d '{
    "operator_confirmed": true,
    "activation_mode": "ready",
    "allow_physical": false,
    "reason": "activate discovered digital twin"
  }'
```

Regola importante: `Ready Virtual` deve funzionare per qualunque digital twin
scoperto da Cyberwave. `Arm Physical` resta invece limitato ai robot con adapter
SafeGround locale, runtime `live`, `dry_run=false`, operatore presente e check
fisici completati.

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
5. Dal pannello videocamera disattivare eventuali feed non necessari con `Disable camera`, poi marcare il target con `Mine`, `Not mine` o `Uncertain` e verificare `OBJECT_MARKED` in timeline.
6. Usare `Command Palette` con: `ispeziona il campo in cerca di mine`.
7. Premere `Stop All` per dimostrare override umano.
8. Usare `Safety -> Runtime` per passare tra `mock`, `simulation` e `live`.
9. Disattivare `Dry run` solo dopo conferma operatore e check fisici.
10. Aprire `Robot Activation`, verificare i twin Cyberwave disponibili e premere `Ready Virtual`.
11. In `simulation` o dry-run, usare `Base Movement P0 -> Movement target: Virtual` per muovere i twin nella dashboard Cyberwave.
12. In `live + dry_run=false`, usare `Arm Physical` solo dopo check fisici; i micro-movimenti base pubblicano comandi MQTT `stop -> movimento -> stop`.
13. Usare i pannelli manuali: micro-movimento bounded e SO-101 takeover.
14. Per raccolta oggetto assistita: aprire `Object Pickup Workflow`, premere `Start Recording`, usare SO-101 takeover guardando il feed, poi `Finish / Save` per creare un template riusabile.

## Runtime Mock / Simulation / Live

Il backend parte in modo sicuro con `mock + dry_run=true`:

```bash
.venv/bin/uvicorn safeground.api.server:app --reload
```

Dalla Web UI aprire il pannello `Safety` e usare il selettore `Runtime`:

- `mock`: usa solo fixture e adapter mock;
- `simulation`: usa il percorso SafeGround/Cyberwave simulation per testare i digital twin;
- `live`: prepara il runtime live, da usare solo con operatore presente;
- `Keep dry-run enabled`: deve restare attivo per rehearsal e simulation non distruttive.

Per testare l'app in simulation dalla API:

```bash
curl -X POST http://localhost:8000/api/runtime \
  -H 'Content-Type: application/json' \
  -d '{
    "runtime_mode": "simulation",
    "dry_run": true,
    "operator_confirmed": true,
    "reason": "test SafeGround against Cyberwave digital twins"
  }'
```

Per passare a live non dry-run via API:

```bash
curl -X POST http://localhost:8000/api/runtime \
  -H 'Content-Type: application/json' \
  -d '{
    "runtime_mode": "live",
    "dry_run": false,
    "operator_confirmed": true,
    "reason": "supervised live smoke test"
  }'
```

Nota safety: lo switch aggiorna configurazione, snapshot, robot card e audit log.

## Robot Activation E Movimento Virtuale/Fisico

Discovery dei robot Cyberwave disponibili:

```bash
curl http://localhost:8000/api/cyberwave/robots
```

Attivazione virtuale di Go2:

```bash
curl -X POST http://localhost:8000/api/robots/go2/activate \
  -H 'Content-Type: application/json' \
  -d '{
    "operator_confirmed": true,
    "activation_mode": "ready",
    "allow_physical": false,
    "reason": "virtual dashboard test"
  }'
```

Attivazione virtuale di un digital twin generico scoperto da Cyberwave:

```bash
ROBOT_ID=<robot_id-from-api-cyberwave-robots>
curl -X POST "http://localhost:8000/api/robots/${ROBOT_ID}/activate" \
  -H 'Content-Type: application/json' \
  -d '{
    "operator_confirmed": true,
    "activation_mode": "ready",
    "allow_physical": false,
    "reason": "virtual activation for discovered Cyberwave digital twin"
  }'
```

`Ready Virtual` non richiede hardware fisico ne' adapter locale SafeGround: basta
che il twin sia presente nella discovery Cyberwave. Serve per dashboard,
simulation, pose virtuale e test dei flussi UI. Se invece il robot non e'
scoperto e non e' nella fleet mock locale, l'API risponde `404`.

Movimento virtuale del twin nella dashboard Cyberwave:

```bash
curl -X POST http://localhost:8000/api/robots/go2/move \
  -H 'Content-Type: application/json' \
  -d '{
    "action": "move_forward",
    "movement_target": "virtual",
    "operator_confirmed": true,
    "distance_m": 0.25
  }'
```

Comando movimento Go2 assistito da agente/FSM:

```bash
curl -X POST http://localhost:8000/api/robots/go2/movement-command \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "avanti",
    "robot_id": "go2",
    "movement_target": "virtual",
    "operator_confirmed": true,
    "distance_m": 0.25,
    "angle_degrees": 10
  }'
```

Il comando testuale viene convertito solo in micro-azioni allow-list (`move_forward`, `move_backward`, `rotate_left`, `rotate_right`) e attraversa la FSM:

```text
IDLE -> PLANNING -> PLANNED -> SAFETY_CHECKED -> EXECUTING -> COMPLETED
```

In caso di comando non valido o safety failure va in `REJECTED`; se l'operatore ferma Go2 va in `STOPPED`.

Stop diretto del solo Go2:

```bash
curl -X POST http://localhost:8000/api/robots/go2/stop
```

Per movimento fisico, prima portare il runtime a `live + dry_run=false`, poi
armare il robot:

```bash
curl -X POST http://localhost:8000/api/robots/go2/activate \
  -H 'Content-Type: application/json' \
  -d '{
    "operator_confirmed": true,
    "activation_mode": "armed",
    "allow_physical": true,
    "reason": "supervised physical smoke test"
  }'
```

Nota safety: `physical` e `both` sono bloccati se il robot non e' armato,
se `dry_run=true`, se il runtime non e' `live`, o se il `robot_id` indica solo
un digital twin scoperto senza adapter fisico SafeGround locale.

### Tastiera Web UI

Premere `?` nella Web UI per aprire l'overlay completo. Nel pannello
`Base Movement P0`, abilitare `Enable keyboard driving` prima di usare tasti di
movimento: ogni pressione invia un solo micro-comando bounded; tenere premuto un
tasto non genera uno stream continuo.

Mappatura safety-first:

- `W` / `ArrowUp`: Go2 `move_forward`.
- `S` / `ArrowDown`: Go2 `move_backward`.
- `Shift+A`: Go2 `strafe_left`.
- `Shift+D`: Go2 `strafe_right`.
- `A` / `ArrowLeft`: Go2 `rotate_left`.
- `D` / `ArrowRight`: Go2 `rotate_right`.
- `Space`: `Stop All`.
- `Esc`: chiude l'overlay se aperto, disabilita Keyboard Drive e invoca `Stop All`.
- `F`: avvia `Start Field Scan`.
- `Ctrl/Cmd+K`: porta il focus sulla `Command Palette`.
- `Ctrl/Cmd+Enter`: invia il comando solo quando la `Command Palette` ha focus.
- `M`, `N`, `U`: marcano l'ultima osservazione come `MINE`, `NOT_MINE` o `UNCERTAIN`.
- `R`: pianifica la route Go2 disegnata se ci sono almeno due waypoint.
- `C`: svuota la draft route solo quando Keyboard Drive e' disattivato.
- `H`: invia `hold_position` a SO-101 se il pannello/twin e' disponibile.

I tasti globali sono ignorati mentre il focus e' su input, select, textarea,
button o campi editabili, tranne `Ctrl/Cmd+K`, `Ctrl/Cmd+Enter` ed `Esc` dove
serve un comportamento browser-operativo esplicito. Le azioni fisiche restano
vincolate a runtime `live + dry_run=false` e robot armato.

### Frame Go2 In Web UI

Il pattern Cyberwave validato per leggere l'immagine corrente e' equivalente al notebook Colab:

```python
from cyberwave import Cyberwave

cw = Cyberwave(api_key=CYBERWAVE_API_KEY, environment_id=CYBERWAVE_ENVIRONMENT)
cw.affect("live")  # oppure "simulation" in dry-run
dog = cw.twin(
    twin_id="758bee49-6668-4733-80f8-da1c0a7134b2",
    environment_id=CYBERWAVE_ENVIRONMENT,
)
img_bytes = dog.get_latest_frame()  # alias di get_frame(source="cloud")
```

SafeGround risolve automaticamente `CYBERWAVE_ENVIRONMENT` da `~/.cyberwave/environment.json`
se non e' presente in `.env`, mappa il robot al twin UUID locale e rifiuta payload JSON
d'errore mascherati da immagine.

Nel backend SafeGround questo viene esposto come endpoint read-only:

```text
GET /api/robots/go2/latest-frame
```

La Web UI usa l'endpoint nel pannello camera quando il runtime e' `simulation` o `live`, aggiornando l'immagine con cache-busting. Non avvia movimenti: la riga demo `dog.move_forward()` del notebook non va usata per mostrare frame o video.

### Disattivazione Selettiva Camere

Nel pannello `Latest Frame`, ogni stream Cyberwave ha un pulsante
`Disable camera` / `Enable camera`. La disattivazione e' locale alla Web UI:
nasconde il feed e smette di renderizzare l'immagine MJPEG nel browser, ma non
spegne il device, il driver Edge o la registrazione Cyberwave. Usare `Enable all`
per riattivare tutti i feed visibili nella dashboard.

### Debug Feed/Frame Mancanti

Se la camera e' accesa ma la Web UI non mostra feed o frame:

1. Verificare che backend e frontend siano entrambi attivi:

```bash
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8000/api/camera-streams
```

2. Se `/api/camera-streams` ritorna URL tipo `http://localhost:8091`, verificare
   che la porta risponda davvero:

```bash
python - <<'PY'
import urllib.request
for port in (8091, 8092):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}", timeout=3) as response:
            print(port, response.status, response.headers.get("content-type"))
    except Exception as exc:
        print(port, type(exc).__name__, exc)
PY
```

3. Se le porte rispondono `Connection refused`, il problema e' nel processo camera
   Cyberwave/ffmpeg/driver, non nel rendering Vue. Controllare:

```bash
cyberwave edge cameras
cyberwave edge status
cyberwave worker status
cyberwave worker doctor --no-runtime
```

4. Per il box `Latest Frame`, assicurarsi di essere in `simulation` o `live` e di
   avere credenziali SDK disponibili:

```bash
export CYBERWAVE_API_KEY=<api-key>
export CYBERWAVE_ENVIRONMENT=<environment-id>
curl http://127.0.0.1:8000/api/robots/go2/latest-frame --output /tmp/go2-frame.jpg
```

## Object Pickup Workflow

La raccolta oggetto e' codificata come record/replay supervisionato:

1. `Start Recording` registra lo step Go2 `stand_down` / postura bassa come movimento composto prevalidato.
2. Il pannello camera mostra i feed configurati da Cyberwave.
3. L'operatore usa `SO-101 Takeover`; ogni comando manuale viene aggiunto alla sessione.
4. `Finish / Save` salva il template in `safeground_runs/object_pickup_sessions.json`.
5. `Reuse Template` seleziona la sequenza e registra un replay auditable, senza esecuzione autonoma YOLO.

API:

```bash
curl -X POST http://localhost:8000/api/object-pickup/start \
  -H 'Content-Type: application/json' \
  -d '{"operator_confirmed": true, "object_label": "safe_object"}'
```

La futura fase YOLO dovra' usare lo stesso template solo dopo validazione su target `NOT_MINE`, workspace libero e conferma operatore.

### MQTT Movement Bridge

Quando `runtime_mode=live` e `dry_run=false`, i comandi base dei robot mobili non restano mock: vengono pubblicati via MQTT al controller policy.

Default backend:

```text
host: localhost
port: 1883
topic: safeground/robots/{robot_id}/commands
qos: 1
```

Ogni micro-movimento pubblica tre messaggi:

```text
stop_before_motion -> move_forward/move_backward/rotate_left/rotate_right -> stop_after_motion
```

Payload essenziale:

```json
{
  "source": "safeground",
  "robot_id": "go2",
  "runtime_mode": "live",
  "dry_run": false,
  "sequence_step": "move_forward",
  "action": "move_forward",
  "distance_m": 0.25,
  "angle_degrees": 10,
  "operator_id": "operator"
}
```

Prima del live verificare broker, topic reale, controller policy/action list e comportamento dello stop sul robot fisico.

### Cyberwave YOLO Can Color Workflow

Workflow Cyberwave creato da CLI:

```text
name: SafeGround Can Color Triage
uuid: add9b071-ac39-4c3c-9fe1-41d410ffab72
template: object-detection
url: https://cyberwave.com/workflows/add9b071-ac39-4c3c-9fe1-41d410ffab72
```

Stato operativo:

- il workflow remoto esiste ed e' attivo, ma va ancora completato nell'editor Cyberwave con environment, twin e nodi camera/model;
- il worker edge custom e' installato come `safeground_can_color_triage.py`;
- il modello locale bindato e' `yoloe-26n-seg.pt`, camera `default`, twin UGV Beast `8a40ed9f-349c-44d2-98c0-3a2282134839`;
- il worker ascolta anche il twin Go2 `758bee49-6668-4733-80f8-da1c0a7134b2` come Verification Scout.

Mapping SafeGround:

```text
lattina verde    -> NOT_MINE / SAFE / REPORT
lattina arancione -> MINE / DANGER / REPORT
lattina nera     -> UNCERTAIN / DOUBT / SECOND_VIEW
```

Reinstall worker e binding modello:

```bash
cyberwave worker add cyberwave_workers/safeground_can_color_triage.py --force
cyberwave model bind \
  --model yoloe-26n-seg.pt \
  --camera default \
  --twin-uuid 8a40ed9f-349c-44d2-98c0-3a2282134839 \
  --confidence 0.4 \
  --fps 3 \
  --classes "can,soda can,tin can,bottle,cup" \
  --env-file "$HOME/.cyberwave/safeground-models.env"
```

Verifiche:

```bash
cyberwave worker list --json
cyberwave model show --env-file "$HOME/.cyberwave/safeground-models.env"
cyberwave worker status
```

Dry-run con replay video/frames Cyberwave:

```bash
.venv/bin/python -m safeground.cli \
  --replay-recording /data/recordings/session_001 \
  --replay-channel frames/default \
  --replay-speed 1.0
```

Script equivalente:

```bash
.venv/bin/python scripts/replay_cyberwave_recording.py \
  /data/recordings/session_001 \
  --channel frames/default \
  --speed 1.0
```

Questo usa `cyberwave.data.recording.replay()` e ripubblica i frame registrati
sugli stessi canali locali ascoltati dal worker (`@cw.on_frame(...,
sensor="default")`). E' dry-run SafeGround: non avvia missioni e non invia
comandi motore; serve solo a testare il modello locale su un video/recording
gia' acquisito.

Nota safety: il worker pubblica eventi `safeground_can_triage` e non invia comandi motore. La lattina nera richiede seconda osservazione da altro robot; non va toccata da SO-101 o da operatori durante la demo.

## Collegamento Go2 (solo su richiesta esplicita)

Procedura manuale da usare solo se decisa dall'operatore. Non eseguire questi comandi automaticamente durante setup, test o demo mock.

Accesso SSH al Go2:

```bash
ssh -p 29839 gobox@2.tcp.eu.ngrok.io
```

Password:

```text
gobox123
```

Per sganciare sessioni attive o con utenti vecchi:

```bash
sudo cyberwave edge uninstall --channel staging
```

Risposte alle domande interattive:

```text
prima domanda: y
seconda domanda: n
```

Poi eseguire il pairing confermando alle domande:

```bash
sudo cyberwave pair
```

Durante il pairing selezionare sempre:

```text
Environment: Default environment
```

Alla domanda `Which twins are physically connected to your edge?`, abilitare tutti i robot mostrati:

```text
[x] Unitree Go2 (758bee49...)
[x] SO-101 Go2 (577e2d72...)
[x] UGV Beast (8a40ed9f...)
[x] SO-101 UGV (33b64f26...)
```

## Comandi Chat

I comandi chat vengono interpretati in intenti strutturati prima di raggiungere la mission state machine.

```bash
.venv/bin/python -m safeground.cli --command "ispeziona il campo in cerca di mine"
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
.venv/bin/python -m safeground.cli --command "ispeziona il campo in cerca di mine" --print-events
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
- La lista completa dei movimenti possibili non coincide con la lista abilitata
  in P0; vedere `docs/robot_movement_capability_map.md`.
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
