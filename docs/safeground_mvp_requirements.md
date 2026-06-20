# SafeGround AI — MVP Requirements

## 1. Obiettivo

Realizzare un MVP multi-robot che dimostri **interazione orchestrata tra robot tramite agenti LLM** in uno scenario simulato di mine-action triage.

Il sistema deve:

1. esplorare una zona tramite un robot mobile;
2. acquisire immagini e dati disponibili dai sensori;
3. classificare un oggetto osservato come:
   - `MINE`
   - `NOT_MINE`
   - `UNCERTAIN`
4. in caso di `UNCERTAIN`, incaricare automaticamente un secondo robot di effettuare una seconda osservazione;
5. fondere le osservazioni;
6. registrare posizione, immagini, classificazione, confidenza e motivazione;
7. mostrare tutto in tempo reale in un’interfaccia web;
8. consentire sempre stop, takeover umano e conferma manuale.

> Scope di sicurezza: l’MVP opera esclusivamente con oggetti scenici/inerti. Non rileva esplosivi reali, non manipola oggetti sospetti e non simula procedure di disinnesco.

---

## 2. Value proposition

**SafeGround AI coordina robot eterogenei per ispezionare una zona potenzialmente contaminata, identificare oggetti sospetti, richiedere una seconda opinione quando l’osservazione è incerta e produrre una mappa di rischio verificabile.**

Il valore principale della demo non è la sola computer vision, ma il ciclo completo:

```text
Sense → Classify → Decide → Delegate → Verify → Report
```

---

## 3. Demo target

### Scenario

Una zona di prova contiene:

- oggetti chiaramente riconoscibili come mine simulate;
- oggetti chiaramente innocui;
- oggetti ambigui o parzialmente occultati;
- ostacoli semplici;
- una griglia o mappa con coordinate relative.

### Flusso demo

```text
1. Operatore avvia la missione dalla dashboard.
2. Go2 esplora il settore A.
3. Go2 acquisisce un frame.
4. Vision Agent classifica l’oggetto.
5. Se MINE:
   - registra hazard;
   - aggiorna la mappa;
   - mantiene distanza di sicurezza;
   - opzionalmente attiva il Marker Agent.
6. Se NOT_MINE:
   - registra l’osservazione;
   - registra la traccia percorsa come route safe riusabile;
   - prosegue.
7. Se UNCERTAIN:
   - Orchestrator assegna la verifica a UGV Beast;
   - UGV usa la route safe del robot primario per raggiungere il settore;
   - UGV raggiunge un punto di osservazione alternativo;
   - acquisisce un secondo frame;
   - Verification Agent fonde le due osservazioni.
8. SO101, come feature aggiuntiva, posiziona un marker su una mappa fisica o deposita un segnale fuori dalla zona di rischio.
9. Dashboard mostra timeline, immagini, decisioni, robot impiegati e risultato finale.
```

---

## 4. Ruoli dei robot

| Robot | Ruolo MVP | Responsabilità |
|---|---|---|
| Unitree Go2 | Primary Scout | Esplorazione, attraversamento ostacoli, acquisizione primaria, mapping/pose se disponibile |
| UGV Beast | Verification Scout | Seconda osservazione stabile da angolo differente, conferma o rigetto del sospetto |
| SO101 | Marker Agent | Posizionamento di marker scenici su mappa fisica o in una zona sicura |
| Camera fissa/opzionale | Overview Sensor | Vista globale, validazione della posizione e registrazione della demo |

### Strategia di fallback

- Solo Go2 disponibile: seconda osservazione eseguita dallo stesso robot da una posa diversa.
- Solo UGV disponibile: UGV esegue osservazione primaria e secondaria da due waypoint.
- SO101 non disponibile: marking solo digitale sulla dashboard.
- Camera onboard non accessibile: usare una Standard Camera associata al twin o una camera fissa.

---

## 5. Sensoristica disponibile

### 5.1 Unitree Go2

#### Confermato dalla documentazione Cyberwave

Cyberwave indica che, dopo il pairing, il robot può esporre:

- feed video;
- nuvola di punti LiDAR;
- audio;
- pose;
- joint states;
- altri sensori esposti dal driver;
- occupancy map costruita da LiDAR e camera.

#### Confermato dalla documentazione Unitree

- 4D LiDAR L2:
  - campo visivo dichiarato: `360° × 96°`;
  - distanza minima dichiarata: `0,05 m`;
- camera HD grandangolare;
- 12 motori articolari;
- stato articolare disponibile tramite integrazione Cyberwave;
- sensore di forza ai piedi solo su alcune configurazioni, in particolare da verificare sul modello EDU;
- modulo di posizionamento vettoriale disponibile in base alla variante;
- eventuale depth camera disponibile sulla variante EDU/configurazioni dedicate.

#### Verifiche da fare subito sul posto

- variante esatta: AIR, PRO, X o EDU;
- disponibilità effettiva di:
  - LiDAR point cloud;
  - camera onboard;
  - audio;
  - foot force;
  - depth camera;
  - odometria/pose;
  - occupancy map;
- frequenza e latenza dei canali;
- lista delle action esposte dal twin;
- supporto waypoint/autonomous navigation già configurato.

### 5.2 UGV Beast

#### Confermato dalla documentazione pubblica Cyberwave

- locomozione autonoma;
- missioni a waypoint;
- raccolta di input visuale;
- integrazione con workflow AI per analisi delle immagini.

#### Da verificare sul posto

La documentazione pubblica consultata non specifica in modo affidabile il corredo completo dell’UGV Beast. Verificare:

- camera RGB;
- camera depth;
- LiDAR;
- sensori di distanza;
- IMU;
- encoder ruote;
- odometria;
- pan/tilt camera;
- pose e stato batteria;
- disponibilità di occupancy map;
- controlli disponibili:
  - velocity;
  - relative move;
  - waypoint;
  - stop;
  - rotate in place.

### 5.3 SO101

#### Confermato

- joint states in tempo reale;
- controllo dei giunti per posizione;
- API con supporto a posizione, velocità e accelerazione;
- teleoperazione leader/follower;
- camera USB/IP montabile sul polso;
- registrazione sincronizzata di:
  - traiettorie articolari;
  - feed camera;
  - telemetria disponibile;
- collision detection per controller non-teleop;
- calibrazione di zero e range articolari.

#### Da verificare

- nomi reali dei giunti;
- range del gripper;
- eventuale feedback di carico/corrente esposto dal driver;
- presenza effettiva della wrist camera;
- latenza del controllo;
- payload sicuro per i marker usati.

### 5.4 Camera Integration

Cyberwave supporta:

- acquisizione singolo frame;
- frame in formato:
  - file JPEG;
  - NumPy/BGR;
  - PIL;
  - bytes;
- acquisizione batch;
- selezione `sensor_id` su twin multi-camera;
- stream WebRTC;
- Standard Camera;
- Intel RealSense D455 con RGB + depth;
- camera discovery;
- configurazione risoluzione e FPS;
- pipeline edge/cloud per VLM o detector;
- overlay delle detection sul video.

### 5.5 Inventario sensori runtime

All’avvio il backend deve produrre una capability map reale:

```json
{
  "go2": {
    "online": true,
    "sensors": ["camera", "lidar", "pose", "joint_states"],
    "actions": ["move_forward", "rotate", "stop", "capture_frame"]
  },
  "ugv": {
    "online": true,
    "sensors": ["camera", "odometry"],
    "actions": ["relative_move", "rotate", "stop", "capture_frame"]
  },
  "so101": {
    "online": true,
    "sensors": ["joint_states", "wrist_camera"],
    "actions": ["set_joints", "home", "place_marker"]
  }
}
```

La capability map deve essere costruita dal sistema reale, non hardcoded, quando possibile.

---

## 6. Architettura

```text
┌──────────────────────────────┐
│          Web UI              │
│ missione, stream, mappa, stop│
└──────────────┬───────────────┘
               │ WebSocket/SSE + REST
┌──────────────▼───────────────┐
│        FastAPI Backend       │
│ state machine + event store  │
└───────┬─────────┬────────────┘
        │         │
┌───────▼───┐ ┌───▼──────────────┐
│Orchestrator│ │ Safety Governor  │
│Agent / LLM │ │ deterministic    │
└───────┬────┘ └───┬──────────────┘
        │           │
┌───────▼───────────▼────────────┐
│       Mission State Machine    │
└───────┬─────────┬──────────────┘
        │         │
┌───────▼───┐ ┌───▼──────────────┐
│Vision Agent│ │Verification Agent│
└───────┬────┘ └───┬──────────────┘
        │           │
┌───────▼───────────▼────────────┐
│      Cyberwave Robot Adapters  │
│ Go2 | UGV | SO101 | Camera     │
└────────────────────────────────┘
```

### Decisione architetturale

L’LLM deve produrre solo:

- piani ad alto livello;
- selezione del robot;
- spiegazione;
- richiesta di verifica;
- output strutturato.

L’LLM **non deve inviare direttamente comandi motore liberi**.

L’esecuzione deve passare da:

1. schema validation;
2. capability check;
3. safety policy;
4. deterministic executor;
5. timeout;
6. telemetry feedback.

---

## 7. Agenti

### 7.1 Orchestrator Agent

Responsabilità:

- ricevere missione e stato;
- scegliere il robot in base alle capacità;
- creare task;
- gestire handoff;
- richiedere una seconda opinione;
- terminare o mettere in pausa la missione.

Output:

```json
{
  "decision": "REQUEST_SECOND_OPINION",
  "assigned_robot": "ugv",
  "reason": "primary confidence below threshold",
  "target": {
    "sector": "B2",
    "relative_position": [1.4, 0.8]
  },
  "constraints": {
    "do_not_contact_target": true,
    "max_speed_mps": 0.3
  }
}
```

### 7.2 Vision Agent

Input:

- frame;
- eventuale depth;
- contesto della missione;
- lista classi ammesse.

Output obbligatoriamente strutturato:

```json
{
  "label": "UNCERTAIN",
  "confidence": 0.61,
  "bbox": [120, 90, 320, 260],
  "evidence": [
    "round object partially covered",
    "insufficient view of top surface"
  ],
  "recommended_action": "SECOND_VIEW"
}
```

### 7.3 Verification Agent

Responsabilità:

- confrontare osservazione primaria e secondaria;
- valutare accordo/disaccordo;
- produrre risultato finale;
- richiedere human review quando necessario.

Regole MVP:

```text
- Due MINE concordi → CONFIRMED_MINE
- Due NOT_MINE concordi → CLEARED_OBJECT
- Una osservazione UNCERTAIN → HUMAN_REVIEW
- Disaccordo MINE / NOT_MINE → HUMAN_REVIEW
- Frame non valido → RETRY_CAPTURE
```

### 7.4 Marker Agent

Responsabilità:

- associare il target a una cella della mappa;
- inviare a SO101 una sequenza pre-validata;
- posizionare un marker scenico;
- tornare in home;
- non avvicinare il braccio a oggetti sospetti.

Takeover umano SO101:

- la dashboard può mettere il braccio in modalità `human takeover`;
- l'operatore può inviare solo azioni discrete e bounded: `home`, `hold_position`, `nudge_joint`, `place_safe_marker`;
- ogni `nudge_joint` è limitato a un piccolo delta e a giunti allow-listati;
- `place_safe_marker` è consentito solo su target `NOT_MINE` e usa una posa prevalidata fuori dalla zona di rischio;
- ogni comando richiede conferma operatore e viene registrato nell'event log.

### 7.5 Safety Governor

Componente deterministico, non LLM.

Regole minime:

- emergency stop sempre disponibile;
- nessun contatto con target sospetto;
- ogni robot mobile registra la traccia percorsa come audit trail;
- una traccia e' considerata safe e riusabile finche' non attraversa una mina confermata;
- se un robot mobile passa sopra una mina, la traccia viene invalidata e non puo' essere usata da altri robot;
- SO101 e' escluso dalla regola di locomozione sopra mina perche' e' un braccio fisso/marker agent, ma resta soggetto al divieto di contatto con `MINE` e `UNCERTAIN`;
- velocità massima per robot;
- timeout per ogni movimento;
- movimenti base P0 limitati a micro-step: massimo 0,5 m o 15 gradi per comando;
- allowlist di azioni;
- un solo comando di locomozione attivo per robot;
- stop automatico prima di capture;
- stop in caso di stream o telemetria persa;
- richiesta conferma umana per azioni fisiche P1/P2;
- esclusione di backflip, salto e skill acrobatiche.

---

## 8. State machine

```text
IDLE
  ↓
MISSION_CREATED
  ↓
PRIMARY_ROBOT_DISPATCHED
  ↓
OBSERVING
  ↓
CLASSIFYING
  ├── MINE ───────────────→ HAZARD_RECORDED
  ├── NOT_MINE ───────────→ OBJECT_CLEARED
  └── UNCERTAIN ──────────→ SECOND_ROBOT_DISPATCHED
                               ↓
                         SECOND_OBSERVATION
                               ↓
                           CONSENSUS
                         ├── CONFIRMED
                         └── HUMAN_REVIEW
                               ↓
                            REPORTED
                               ↓
                           NEXT_TARGET
                               ↓
                            COMPLETE
```

---

## 9. Computer vision

### Strategia MVP

Per velocità:

1. VLM multimodale con risposta JSON;
2. opzionale detector YOLO se è disponibile un modello già pronto;
3. nessun training custom durante il critical path;
4. dataset scenico controllato;
5. immagini da due angoli per i casi ambigui.

### Classificazione

Classi consentite:

```text
MINE
NOT_MINE
UNCERTAIN
```

Soglie iniziali:

- risultato accettato se `confidence >= 0.75`;
- sotto soglia: `UNCERTAIN`;
- conflitto tra due robot: human review;
- immagine sfocata/occlusa: retry o nuova posa.

> La confidence prodotta da un VLM è un’indicazione operativa, non una probabilità calibrata. La demo deve usare anche regole di consenso e revisione umana.

### Dataset demo

Preparare almeno:

- 3 mock mine chiaramente visibili;
- 3 non-mine;
- 2 oggetti ambigui;
- 1 oggetto parzialmente coperto;
- 1 caso con illuminazione difficile.

---

## 10. Web application

### Stack consigliato

Per velocità:

- Backend: FastAPI;
- Runtime events: WebSocket o Server-Sent Events;
- Frontend:
  - Streamlit per MVP rapidissimo, oppure
  - Vue 3/Vite per demo più curata;
- Storage: SQLite o JSONL;
- immagini: filesystem locale;
- orchestrazione: Python asyncio;
- modelli dati: Pydantic.

### Schermata principale

#### Header

- nome missione;
- stato;
- timer;
- pulsante `START`;
- pulsante `PAUSE`;
- pulsante `EMERGENCY STOP`.

#### Robot cards

Per ogni robot:

- online/offline;
- ruolo;
- task corrente;
- batteria se disponibile;
- sensori disponibili;
- ultimo heartbeat;
- modalità:
  - autonomous;
  - human takeover;
  - idle;
  - error.

#### SO101 human takeover

- pannello dedicato visibile dalla dashboard;
- pulsanti `Home`, `Hold`, `Safe Marker`;
- selezione giunto e step bounded per piccoli aggiustamenti manuali;
- nessun comando raw libero verso i giunti;
- risultato comando e safety check visibili nella timeline.

#### Camera panel

- feed Go2;
- feed UGV;
- camera overview;
- bounding box;
- label;
- confidence;
- pulsante `Request second opinion`.

#### Risk map

- posizione robot;
- percorso;
- target osservati;
- stato:
  - rosso: mine;
  - verde: not mine;
  - giallo: uncertain;
- immagine associata;
- robot che ha effettuato la verifica.

#### Timeline

```text
10:12:04 Mission started
10:12:11 Go2 dispatched to sector B2
10:12:19 Frame captured
10:12:22 Result: UNCERTAIN 0.61
10:12:23 UGV assigned for second opinion
10:12:41 UGV frame captured
10:12:44 Consensus: MINE
10:12:46 Hazard recorded
```

---

## 11. API interne

### Mission

```http
POST /api/missions
POST /api/missions/{id}/start
POST /api/missions/{id}/pause
POST /api/missions/{id}/stop
GET  /api/missions/{id}
```

### Robots

```http
GET  /api/robots
GET  /api/robots/{id}/capabilities
POST /api/robots/{id}/dispatch
POST /api/robots/{id}/stop
POST /api/robots/{id}/capture
```

### Observations

```http
POST /api/observations
GET  /api/observations/{id}
POST /api/observations/{id}/verify
POST /api/observations/{id}/human-review
```

### Events

```http
GET /api/events
WS  /ws/events
```

---

## 12. Modello dati

### Observation

```json
{
  "id": "obs_001",
  "mission_id": "mission_001",
  "robot_id": "go2",
  "sensor_id": "front_camera",
  "timestamp": "2026-06-20T10:12:19Z",
  "sector": "B2",
  "pose": {
    "x": 1.4,
    "y": 0.8,
    "yaw": 1.57
  },
  "image_path": "captures/obs_001.jpg",
  "classification": {
    "label": "UNCERTAIN",
    "confidence": 0.61,
    "evidence": ["partial occlusion"]
  }
}
```

### Finding

```json
{
  "id": "finding_001",
  "status": "CONFIRMED_MINE",
  "sector": "B2",
  "observations": ["obs_001", "obs_002"],
  "verified_by": ["go2", "ugv"],
  "human_review": false,
  "marker_status": "DIGITAL_ONLY"
}
```

---

## 13. Priorità

## P0 — Must have

Queste feature definiscono il prodotto minimo dimostrabile.

| ID | Requisito | Criterio di accettazione |
|---|---|---|
| P0.1 | Collegamento Cyberwave | Almeno un robot e una camera risultano online |
| P0.2 | Frame capture | Backend acquisisce un frame tramite SDK |
| P0.3 | Classificazione | Frame classificato in uno dei tre stati |
| P0.4 | Output JSON validato | Risposta CV passa schema Pydantic |
| P0.5 | State machine | Missione attraversa almeno IDLE → OBSERVE → CLASSIFY → REPORT |
| P0.6 | Dashboard | Visualizza robot, frame, stato e classificazione |
| P0.7 | Event log | Ogni azione viene registrata |
| P0.8 | Safety | Stop manuale e timeout funzionanti |
| P0.9 | Mock mode | Tutto il flusso funziona senza hardware reale |
| P0.10 | Demo script | Una missione completa è ripetibile |
| P0.11 | Movimenti base bounded | Dashboard/API eseguono avanti, indietro e rotazioni brevi con conferma operatore, stop-wrapping e audit log |

## P1 — Premio principale

Queste feature dimostrano vera interazione multi-robot.

| ID | Requisito | Criterio di accettazione |
|---|---|---|
| P1.1 | Second opinion | `UNCERTAIN` attiva automaticamente un secondo robot |
| P1.2 | Handoff | Il secondo robot riceve target e task dal primo |
| P1.3 | Alternate viewpoint | Secondo frame ottenuto da posizione/angolo diverso |
| P1.4 | Consensus | Due osservazioni producono un finding unico |
| P1.5 | Risk map | Finding mostrato sulla mappa |
| P1.6 | Human review | Disaccordo richiede scelta operatore |
| P1.7 | Live telemetry | UI aggiornata via WebSocket/SSE |
| P1.8 | Capability-aware routing | Orchestrator seleziona robot in base ai sensori disponibili |

## P2 — Wow factor

| ID | Requisito | Criterio di accettazione |
|---|---|---|
| P2.1 | SO101 marker | Braccio posiziona un marker scenico |
| P2.2 | LiDAR/map | Posizione target collegata a occupancy map |
| P2.3 | Multi-camera | Camera overview conferma la missione |
| P2.4 | Overlay | Bounding box e label visibili sul feed |
| P2.5 | Voice mission | Missione avviabile con comando vocale |
| P2.6 | Explainability | Dashboard mostra perché è stato scelto un robot |
| P2.7 | Replay | Missione rieseguibile dalla timeline |

## P3 — Dopo la demo

- detector custom;
- training/fine-tuning;
- sensor fusion RGB + depth + LiDAR;
- pianificazione autonoma avanzata;
- più target simultanei;
- semantic map;
- metriche di accuratezza;
- deployment edge;
- alert remoti;
- procedure esterne recuperate via ScrapeGraphAI;
- social/human signal integration.

---

## 14. Piano di esecuzione rapido

### Fase 1 — 30 minuti

- ottenere API key;
- installare SDK;
- elencare twins;
- verificare robot online;
- leggere capability/surface disponibili;
- catturare un frame;
- testare stop.

### Fase 2 — 60 minuti

- creare adapter Cyberwave;
- creare mock adapter;
- implementare schema `ClassificationResult`;
- collegare VLM;
- salvare immagini e risultati.

### Fase 3 — 60 minuti

- implementare state machine;
- implementare `UNCERTAIN → second robot`;
- implementare consensus;
- testare con immagini statiche.

### Fase 4 — 60 minuti

- dashboard base;
- stream eventi;
- robot cards;
- camera panel;
- timeline.

### Fase 5 — 60–90 minuti

- integrazione secondo robot;
- alternate viewpoint;
- risk map;
- prove end-to-end.

### Fase 6 — Tempo residuo

- SO101 marker;
- overlay;
- voice control;
- pitch;
- video backup.

---

## 15. Struttura repository

```text
safeground/
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── models/
│   │   ├── mission.py
│   │   ├── observation.py
│   │   └── classification.py
│   ├── agents/
│   │   ├── orchestrator.py
│   │   ├── vision.py
│   │   ├── verification.py
│   │   └── marker.py
│   ├── safety/
│   │   └── governor.py
│   ├── robots/
│   │   ├── base.py
│   │   ├── go2.py
│   │   ├── ugv.py
│   │   ├── so101.py
│   │   └── mock.py
│   ├── services/
│   │   ├── cyberwave.py
│   │   ├── event_bus.py
│   │   └── storage.py
│   └── api/
├── frontend/
├── captures/
├── fixtures/
├── tests/
├── requirements.txt
└── README.md
```

---

## 16. Cyberwave SDK — primitive da validare

```python
from cyberwave import Cyberwave

cw = Cyberwave()

go2 = cw.twin("unitree/go2")
ugv = cw.twin("...")
arm = cw.twin("the-robot-studio/so101")
camera = cw.twin("cyberwave/standard-cam")

with cw.affect("live"):
    frame = go2.capture_frame("numpy")
    go2.move_forward(distance=0.5)

# API utili documentate
go2.camera.read()
go2.camera.snapshot()
go2.capture_frames(3, interval_ms=200, format="numpy")

# Movimento relativo
go2.navigation.relative_move(
    [0.5, 0.0, 0.0],
    frame="body",
    metadata={"source": "safeground-orchestrator"}
)

# SO101
arm.joints.list()
arm.joints.get_all()
arm.joints.set("joint_name", 0.2)

# Workflow
run = cw.workflows.trigger(
    "workflow-id",
    inputs={"mission_id": "mission_001"}
)
run.wait(timeout=60)
```

> I nomi esatti dei twin e delle action devono essere letti dall’ambiente dell’hackathon.

---

## 17. Domande immediate agli organizzatori

1. Qual è la variante esatta del Go2?
2. Quali sensori del Go2 sono esposti nel twin?
3. L’occupancy mapping è già attivo?
4. Il Go2 può navigare a waypoint o solo con comandi relativi?
5. Quali sensori sono montati sull’UGV Beast?
6. L’UGV espone pose/odometria?
7. È disponibile una RealSense?
8. SO101 ha una wrist camera?
9. Il driver SO101 espone corrente, carico o solo posizione?
10. È possibile leggere dinamicamente capability e sensor IDs?
11. Esiste un ambiente già calibrato e mappato?
12. Quali comandi richiedono conferma o supervisione?
13. Il team può usare workflow Cyberwave o solo SDK?
14. È disponibile un canale video WebRTC già configurato?
15. Qual è il limite di tempo per accesso al robot durante la demo?

---

## 18. Definition of Done

L’MVP è pronto quando:

- una missione può essere avviata dalla UI;
- almeno un robot si muove;
- acquisisce un’immagine;
- l’immagine viene classificata;
- un caso incerto genera una seconda osservazione;
- il secondo robot viene attivato automaticamente;
- le due osservazioni vengono fuse;
- il risultato appare sulla dashboard;
- tutte le azioni sono nella timeline;
- lo stop manuale interrompe immediatamente la missione;
- la demo può essere eseguita anche in mock mode.

---

## 19. Pitch

> SafeGround AI è un mission commander multi-robot per il triage di aree potenzialmente contaminate. Un primo robot esplora e osserva; quando la visione è incerta, l’orchestratore incarica automaticamente un secondo robot di verificare da un altro punto di vista. Il sistema fonde le osservazioni, aggiorna una mappa del rischio e mantiene sempre controllo umano, audit trail e policy di sicurezza. La demo usa esclusivamente mine simulate e si concentra su survey, verifica e marcatura, non sul disinnesco.

---

## 20. Fonti tecniche

- Cyberwave SO101: https://docs.cyberwave.com/hardware/so101
- Cyberwave UGV Beast: https://docs.cyberwave.com/hardware/ugv/index
- Cyberwave Go2: https://docs.cyberwave.com/hardware/go2/index
- Cyberwave Camera Integration: https://docs.cyberwave.com/hardware/camera/index
- Cyberwave Overview: https://docs.cyberwave.com/overview
- Cyberwave Python SDK: https://github.com/cyberwave-os/cyberwave-python
- Cyberwave Hacker Starter Kit: https://cyberwavehq.notion.site/Cyberwave-Hacker-Starter-Kit-32169631a05380768f88c9d486c747f2
- Unitree Go2: https://www.unitree.com/go2/
