# SafeGround Robot Connection Guide

## Scopo

Questo documento raccoglie le modalita' di collegamento dei robot SafeGround usando:

- documentazione offline del progetto in `docs/`;
- documentazione online Cyberwave consultata durante la sessione;
- note operative da validare sui robot disponibili all'hackathon.

L'obiettivo e' arrivare rapidamente a una connessione osservabile e sicura: twin online, sensori visibili, frame catturabile, stop funzionante. Il movimento live resta disabilitato per default finche' non sono completati safety check e prova supervisionata.

## Fonti Consultate

Offline:

- `docs/safeground_mvp_requirements.md`
- `docs/safeground_p0_development_plan.md`
- `docs/robot-sensors-research.md`
- `docs/physical_setup_activities.md`
- `docs/commands.md`
- `docs/robot_movement_capability_map.md`

Online:

- Cyberwave Hardware Overview: `https://docs.cyberwave.com/overview/connecting-hardware`
- Cyberwave Python SDK: `https://docs.cyberwave.com/sdks/python-sdk`
- Cyberwave Go2 tutorial: `https://docs.cyberwave.com/tutorials/go2-digital-to-physical`
- Cyberwave Robotic Arms: `https://docs.cyberwave.com/overview/robotic-arms`
- Cyberwave SO-101 natural language agent: `https://docs.cyberwave.com/tutorials/so101-natural-language-agent`
- Cyberwave UGV Beast page: `https://docs.cyberwave.com/hardware/ugv/get-started` (la fetch diretta richiede autenticazione; i dettagli sotto sono tratti dagli snippet pubblici e vanno validati onsite)

## Pattern Comune Cyberwave

Cyberwave collega robot e sensori tramite digital twin e Cyberwave Edge.

Flusso generale:

1. Creare o aprire un environment nel dashboard Cyberwave.
2. Aggiungere il robot o sensore da catalogo con `Add from Catalog`.
3. Posizionare il twin in modo coerente con il setup fisico.
4. Installare Cyberwave CLI/Edge sul compute vicino al robot: laptop, Raspberry Pi, Jetson, onboard computer.
5. Eseguire il pairing tra hardware e twin.
6. Verificare edge/driver/log e stato live nel dashboard.
7. Solo dopo: usare Python SDK in `simulation` o `live`.

Comandi base indicati dalla documentazione Cyberwave:

```bash
curl -fsSL https://cyberwave.com/install.sh | bash
cyberwave pair
cyberwave edge logs
```

Per alcuni setup Edge, soprattutto SO-101, la documentazione mostra:

```bash
sudo cyberwave edge install
```

La differenza tra `cyberwave pair` e `cyberwave edge install` dipende dal flusso guidato del device/catalogo. In sede, seguire il prompt Cyberwave e registrare il comando effettivamente riuscito.

## SDK E Modalita' Runtime

Installazione Python:

```bash
pip install cyberwave
```

Extra utili:

```bash
pip install "cyberwave[camera]"
pip install "cyberwave[realsense]"
pip install "cyberwave[microphone]"
```

Uso base:

```python
from cyberwave import Cyberwave

cw = Cyberwave()
cw.affect("simulation")  # comandi verso twin simulato
cw.affect("live")        # comandi verso robot fisico
```

Regole SafeGround:

- Usare `cw.affect("simulation")` per prove iniziali.
- Usare `cw.affect("live")` solo con operatore presente.
- Validare `stop`, frame capture e health prima di locomozione o giunti.
- Dalla console SafeGround usare `Safety -> Runtime` per passare da `mock` a `simulation` o `live`; disattivare `dry_run` solo per smoke test supervisionati.
- In `live + dry_run=false`, i micro-movimenti base SafeGround vengono inviati via MQTT al controller policy: `safeground/robots/{robot_id}/commands` per default, da validare onsite.
- Non inviare comandi motore raw da LLM.
- Registrare `twin_id`, `environment_id`, `sensor_id`, driver attivo e comando di pairing riuscito.

## Asset Slug Attesi

Questi slug derivano dalle fonti Cyberwave consultate e vanno validati con catalogo/dashboard onsite:

| Hardware | Slug/asset probabile | Stato |
| --- | --- | --- |
| Unitree Go2 | `unitree/go2` | confermato negli esempi SDK/docs |
| SO-101 | `the-robot-studio/so101` | confermato negli esempi SDK/docs |
| Standard Camera | `cyberwave/standard-cam` | confermato negli esempi SDK/docs |
| Waveshare UGV Beast | `waveshare/ugv-beast` | probabile da catalog URL, da validare |

Per evitare ambiguita', preferire il recupero via `twin_id` quando il dashboard mostra piu' istanze dello stesso asset.

## Unitree Go2

Ruolo SafeGround: `Primary Scout` o `Verification Scout`.

Collegamento Cyberwave:

1. Dashboard: creare environment e aggiungere Go2 dal catalogo.
2. Posizionare il twin nel layout demo.
3. Sul compute connesso al Go2, installare CLI/Edge.
4. Eseguire pairing guidato verso il twin Go2.
5. Verificare live telemetry, camera, pose, LiDAR/point cloud se esposti.
6. Verificare nel dashboard che la live data aggiorni il digital twin.

SDK smoke test:

```python
from cyberwave import Cyberwave

cw = Cyberwave()
cw.affect("simulation")
go2 = cw.twin("unitree/go2")

# Smoke test non distruttivo: preferire frame/telemetry a movimento.
frame_path = go2.capture_frame()
```

Solo dopo safety rehearsal:

```python
cw.affect("live")
go2 = cw.twin("unitree/go2")
# Usare solo micro-movimenti bounded e stop supervisionato.
# Esempio docs: go2.move_forward(distance=1.0)
```

Da validare onsite:

- variante Go2: Air, Pro, EDU o altra;
- `twin_id` e `environment_id`;
- camera `sensor_id`;
- disponibilita' di LiDAR/point cloud, pose, occupancy map;
- action esposte dal controller policy;
- comportamento dello stop;
- latenza frame e telemetria.

## UGV Beast Rover

Ruolo SafeGround: `Verification Scout` o scout terrestre stabile.

La pagina UGV richiede autenticazione in fetch diretto, ma gli snippet pubblici indicano questo setup:

1. Prima accensione con TF card preconfigurata.
2. Leggere IP dal display OLED del rover.
3. Collegarsi all'hotspot default del robot, indicato come `AccessPopup`.
4. Aprire l'interfaccia web/JupyterLab del rover.
5. Configurare il rover sulla Wi-Fi locale.
6. Abilitare SSH via `raspi-config`.
7. Entrare nel Raspberry Pi del rover:

```bash
ssh ws@<UGV_IP> -p 22
```

8. Se necessario, entrare nel container Docker del rover:

```bash
ssh root@<UGV_IP> -p 23
```

9. Installare/configurare Cyberwave Edge o immagine Docker Cyberwave secondo il prompt del device.
10. Pairing verso il twin UGV Beast nel dashboard.
11. Verificare driver UGV, camera, IMU, batteria e stop.

SDK smoke test, dopo pairing:

```python
from cyberwave import Cyberwave

cw = Cyberwave()
cw.affect("simulation")
ugv = cw.twin("waveshare/ugv-beast")  # slug da validare nel catalogo onsite
frame_path = ugv.capture_frame()
```

Da validare onsite:

- slug asset reale e `twin_id`;
- se il driver Cyberwave UGV e' gia' installato o va lanciato da Docker;
- camera RGB, pan/tilt, IMU, encoder, batteria;
- presenza di LiDAR/OAK-D o solo camera RGB;
- controller policy: `stop`, `capture_frame`, `relative_move`, `rotate`, waypoint;
- IP stabile del rover e accesso SSH;
- porta corretta per host Pi e container;
- se il rover espone latest-frame via Cyberwave o solo stream locale.

## SO-101 Robot Arm

Ruolo SafeGround: `Marker Agent`; non deve toccare target `MINE` o `UNCERTAIN`.

Collegamento Cyberwave:

1. Dashboard: creare environment e aggiungere SO-101 dal catalogo.
2. Aggiungere anche `Standard Camera` se si usa wrist/overhead camera.
3. Se la camera e' wrist-mounted, impostare il camera twin docked al twin SO-101 e parent root sul polso/end-effector.
4. Collegare follower arm via USB-C al laptop, Raspberry Pi o altro edge node.
5. Collegare camera USB se presente.
6. Installare Cyberwave Edge sul compute collegato.
7. Eseguire pairing del twin SO-101 e del camera twin.
8. Calibrare il braccio.
9. Passare il dashboard in Live Mode.
10. Assegnare controller `Keyboard` e verificare piccoli movimenti manuali.
11. Solo dopo il keyboard test, usare SDK o agente.

Comandi online SO-101:

```bash
ssh your_user@raspberry_pi_ip
curl -fsSL https://cyberwave.com/install.sh | bash
sudo cyberwave edge install
```

SDK smoke test in simulation:

```python
from cyberwave import Cyberwave

cw = Cyberwave()
cw.affect("simulation")
arm = cw.twin("the-robot-studio/so101")

print(arm.joints.list())
print(arm.joints.get_all())
arm.joints.set("shoulder_pan", 30, degrees=True)
```

Pattern locale gia' documentato nel progetto:

```python
from cyberwave import Cyberwave

cw = Cyberwave()
so_101 = cw.twin("the-robot-studio/so101")
so_101.edit_position(x=1, y=0, z=0.5)
so_101.edit_rotation(yaw=90)
so_101.joints.arm_joint = 45
```

Nota: preferire `joints.list()` e `joints.set(...)` finche' non sono confermati i nomi reali dei giunti. L'esempio `arm_joint` resta utile come riferimento dato dagli organizzatori, ma va validato sull'istanza reale.

Da validare onsite:

- follower singolo o coppia leader/follower;
- driver attivo, ad esempio `so101-remoteoperate`;
- calibrazione green;
- joint names reali;
- range gripper e limiti giunti;
- camera wrist/overhead e relativo `sensor_id`;
- latenza dei joint command;
- stop e human takeover.

## Standard Camera / Camera Fissa

Ruolo SafeGround: `Overview Sensor`, fallback P0 per frame capture.

Collegamento Cyberwave:

1. Dashboard: aggiungere `Standard Camera` dal catalogo.
2. Collegare camera USB o IP al compute Edge.
3. Installare extra camera:

```bash
pip install "cyberwave[camera]"
```

4. Pairing del camera twin.
5. Avviare o verificare streaming WebRTC.
6. Catturare frame dal twin o dal robot con `sensor_id`.

SDK:

```python
from cyberwave import Cyberwave

cw = Cyberwave()
camera = cw.twin("cyberwave/standard-cam")
frame_path = camera.capture_frame()
```

Multi-camera:

```python
frame = robot.capture_frame("numpy", sensor_id="wrist_cam")
```

Streaming:

```python
import asyncio
from cyberwave import Cyberwave

cw = Cyberwave()
camera = cw.twin("cyberwave/standard-cam")

async def main():
    await camera.stream_video_background()
    try:
        while True:
            await asyncio.sleep(1)
    finally:
        await camera.stop_streaming()
        cw.disconnect()

asyncio.run(main())
```

Da validare onsite:

- camera USB, IP, RealSense o camera onboard;
- `sensor_id`;
- risoluzione/FPS;
- warmup stream prima di `capture_frame`;
- latenza e formato frame;
- permessi OS per camera;
- eventuale `ffmpeg` installato.

## Checklist Operativa In Sede

Per ogni robot compilare:

```text
Robot:
Ruolo:
Asset slug:
Environment ID:
Twin ID:
Edge host:
Edge command riuscito:
Driver attivo:
Sensor IDs:
Frame capture OK:
Stop OK:
Controller policy/action list:
Runtime provato: mock / simulation / live
Note safety:
```

Ordine consigliato:

1. Standard Camera o camera piu' semplice.
2. SO-101 in simulation, poi keyboard live senza target.
3. Go2 in simulation, poi live telemetry/frame senza locomozione.
4. UGV Beast in simulation, poi live telemetry/frame senza locomozione.
5. Un solo micro-movimento supervised per robot mobile, se serve alla demo.
6. Stop test dopo ogni smoke test live.

## Decisione Per SafeGround MVP

Per il demo:

- P0 deve funzionare anche senza hardware, con mock e fixture.
- Il primo collegamento live utile e' frame capture da camera o robot.
- I movimenti base sono requisito P0 come contratto software e simulazione/mock: avanti, indietro, rotazione sinistra/destra.
- La locomozione live P0 resta limitata a un micro-movimento supervisionato solo dopo frame, stop e health check riusciti.
- Go2 e UGV devono usare route sicure registrate per le seconde verifiche.
- SO-101 resta marker agent P2 e non partecipa alla locomozione safe-route.
- Qualsiasi comando live passa da allow-list, timeout, stop e human override.

Per la mappatura completa dei movimenti possibili, distinguendo P0 safe,
Cyberwave live da cablare e azioni vietate, vedere
`docs/robot_movement_capability_map.md`.
