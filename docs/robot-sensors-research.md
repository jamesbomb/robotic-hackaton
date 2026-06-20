# Ricerca Sensoristica Robot Cyberwave Hackathon

## Scopo

Questo documento riassume la sensoristica utile per un MVP hackathon basato su computer vision, classificazione di oggetti mock e interazione multi-robot. Le informazioni combinano documentazione Cyberwave, documentazione dei produttori e fonti tecniche pubbliche.

Nota importante: alcune pagine hardware Cyberwave dirette hanno richiesto autenticazione durante la ricerca automatica. Le specifiche vanno quindi verificate sui robot fisici disponibili in sede, soprattutto varianti, kit montati e sensori opzionali.

## Sintesi Operativa

| Robot/Sensore | Miglior ruolo nel MVP | Sensori chiave | Confidenza |
| --- | --- | --- | --- |
| UGV Beast Rover | Scout principale a terra | Camera 5MP 160 FOV su pan-tilt, IMU, batteria, luci, possibile LiDAR/OAK-D nei kit ROS2 | Alta per camera/IMU base, media per espansioni |
| Unitree Go2 | Second look mobile | LiDAR 4D/3D, camera HD wide-angle, foot force sensors, mic/speaker, connettivita' | Alta per sensori dichiarati dal produttore, media per variante esatta |
| SO-101 Robot Arm | Manipolazione/marker P2 | Joint states, servo telemetry, wrist camera o overhead camera associata | Alta per arm/camera workflow, media per telemetry esatta esposta |
| Standard Camera | Baseline P0 | RGB, eventuale depth/IR se RealSense o camera depth | Alta |

## Cyberwave: Primitive Comuni

Cyberwave tratta robot e sensori come digital twins. Per il nostro MVP questo significa:

- Stesso codice per simulazione e live tramite `cw.affect("simulation")` e `cw.affect("live")`.
- Frame camera accessibili da Python tramite `twin.get_frame(...)`, con sorgenti cloud, edge, local o Zenoh.
- Camera USB, IP, depth, infrared e industriali supportate come twin camera.
- Workflow e Virtual Controller possono inviare comandi ai twin usando controller policy e MQTT.
- Record/replay utili per raccogliere frame, debug e dataset post-demo.

Fonti: [Cyberwave Quickstart](https://docs.cyberwave.com/overview), [Python SDK docs](https://docs.cyberwave.com/overview/tools/python-sdk.md), [Cyberwave Cameras](https://docs.cyberwave.com/overview/cameras.md), [Virtual Controller node](https://docs.cyberwave.com/feature-reference/workflows/virtual-controller.md).

## UGV Beast Rover

### Sensoristica Rilevante

Il Waveshare UGV Beast e' il candidato migliore per scout terrestre P0/P1.

- Camera 5MP ultra-wide con field of view dichiarato 160 gradi.
- Modulo pan-tilt a 2 DOF per orientare la camera.
- IMU 9 assi, tipicamente ICM-20948, per attitude sensing.
- Monitor batteria, citato come INA219 in fonti tecniche.
- Luci/spotlight ad alta luminosita' accanto al pan-tilt.
- ESP32 come sub-controller per PID motori, sensor processing, servos, LED e comunicazione.
- Raspberry Pi 4/5 o variante Jetson come host per AI vision, pianificazione e ROS2.
- Nei kit ROS2 puo' essere presente D500 360 Lidar e OAK-D Lite depth camera, ma va verificato sul kit specifico dell'hackathon.

### Impatto Sul MVP

Uso consigliato:

- P0: usare la camera del rover come feed principale, anche se il rover resta fermo.
- P1: fare micro-movimenti bounded per acquisire seconda prospettiva.
- P1/P2: usare pan-tilt per guardare target senza muovere tutto il rover.
- Safety: sfruttare stop immediato e comandi discreti, non controllo continuo libero via LLM.

Limiti:

- La camera wide-angle puo' distorcere dimensioni e forma degli oggetti ai bordi.
- IMU e batteria aiutano stato robot, ma non bastano per localizzazione precisa.
- Se non c'e' LiDAR/OAK-D nel kit disponibile, non pianificare depth-based navigation come requisito P0.

### Verifiche In Loco

- Il rover monta davvero la camera pan-tilt?
- Il feed e' accessibile via Cyberwave latest-frame o serve stream locale?
- Quali comandi sono mappati nel controller policy?
- Il kit include LiDAR/OAK-D oppure solo camera RGB?
- Quanto spazio libero e' disponibile per micro-movimenti?

### Fonti

- [Cyberwave UGV voice controlled tutorial](https://docs.cyberwave.com/tutorials/ugv-voice-controlled.md)
- [Waveshare UGV Beast wiki](https://www.waveshare.com/wiki/UGV_Beast)
- [Waveshare UGV Beast product page](https://www.waveshare.com/ugv-beast.htm)
- [Open Hardware Directory: Waveshare UGV Beast](https://openhardware.directory/devices/waveshare-ugv-beast)

Confidenza: alta per camera/IMU/controller architecture; media per sensori opzionali del kit.

## Unitree Go2 Dog Robot

### Sensoristica Rilevante

Il Go2 e' il candidato migliore per second look mobile e per mostrare un robot fisicamente diverso dal rover.

- LiDAR 4D/3D ultra-wide. Le fonti citano varianti L1/L2 con circa 360 x 90 o 360 x 96 gradi e distanza minima circa 0.05 m.
- Camera HD wide-angle frontale, citata come 1280 x 720 con FOV circa 120 gradi.
- Foot-end force sensors per contatto e locomozione.
- Wireless vector positioning/tracking module.
- Microfono/intercom e speaker integrato.
- Connettivita' Wi-Fi 6, Bluetooth e in alcune varianti 4G/eSIM.
- Su alcune configurazioni EDU/plus: moduli aggiuntivi come RealSense D435i o Mid-360 LiDAR.

Cyberwave descrive il Go2 come twin con live telemetry, occupancy mapping, mission design ed esecuzione fisica tramite Edge layer.

### Impatto Sul MVP

Uso consigliato:

- P1: secondo robot per osservare un target `dubbio` da altra prospettiva.
- P1: generare una `second_observation` con frame e stato robot.
- P2: usare LiDAR/occupancy mapping come elemento narrativo di situational awareness.
- P2: voce/audio solo come extra, non come requisito centrale.

Limiti:

- La variante esatta del Go2 conta molto: Air/Pro/EDU e accessori cambiano disponibilita' di compute e sensori.
- LiDAR aiuta mapping/ostacoli ma non classifica da solo le mine mock.
- La camera frontale e' piu' utile del LiDAR per la classificazione visuale dei props.

### Verifiche In Loco

- Modello esatto: Air, Pro, EDU o altro?
- Quale LiDAR e' installato?
- Camera e latest-frame sono disponibili tramite Cyberwave?
- Il robot puo' muoversi in sicurezza nell'area demo?
- Sono disponibili comandi mission/waypoint o solo teleop?

### Fonti

- [Cyberwave Go2 digital to physical tutorial](https://docs.cyberwave.com/tutorials/go2-digital-to-physical.md)
- [Unitree Go2 official page](https://unitree-robot.com/go2/index.html)
- [Unitree Go2 shop page](https://shop.unitree.com/products/unitree-go2)
- [Unitree Go2 brochure PDF mirror](https://static.generation-robots.com/media/brochure-unitree-go2-en.pdf)

Confidenza: alta sulle famiglie di sensori dichiarate; media sulla variante disponibile all'hackathon.

## SO-101 Robot Arm

### Sensoristica Rilevante

L'SO-101 non e' un robot di esplorazione, ma e' utile per manipolazione controllata, gesti, marker e dimostrazione di agenti multimodali.

- Arm 6 DOF: 5 giunti + gripper.
- Servo serial bus Feetech STS3215.
- Joint states e traiettorie registrabili in dataset/teleop.
- Setup leader-follower per teleoperazione e raccolta dimostrazioni.
- Wrist camera docked al polso del robot in Cyberwave.
- Camera overhead o frontale come seconda vista della workspace.
- Possibile registrazione sincronizzata di video e joint state per dataset.

Cyberwave documenta due pattern utili:

- Voice + vision agent: voce, camera frame, LLM planner, piano JSON, esecuzione sicura su giunti.
- Teleop dataset: camera wrist/overhead, joint traces, registrazioni e training VLA.

### Impatto Sul MVP

Uso consigliato:

- P0: non necessario.
- P1: possibile visual confirmation se camera wrist inquadra una scena controllata.
- P2: indicare il target sicuro, spostare marker su `non_mine`, o fare gesto di conferma/alert.

Limiti:

- Non usarlo per toccare props classificati `mine` o `dubbio`.
- Serve workspace stabile, calibrazione e limiti conservativi.
- La camera-to-arm calibration metrica e' fuori scope per hackathon rapido.

### Verifiche In Loco

- E' presente una sola arm o coppia leader/follower?
- La camera e' montata sul wrist, overhead o assente?
- Il twin Cyberwave espone joint commands e latest-frame?
- Quali limiti fisici e di collisione sono gia' configurati?

### Fonti

- [Cyberwave SO-101 natural language agent](https://docs.cyberwave.com/tutorials/so101-natural-language-agent.md)
- [Cyberwave SO-101 teleop dataset](https://docs.cyberwave.com/tutorials/so101-teleop-dataset.md)
- [SO-101 specifications](https://www.roboticscenter.ai/hardware/so-101/specs)
- [SO-101 quickstart](https://www.roboticscenter.ai/hardware/so-101/quickstart)

Confidenza: alta sul setup arm/camera; media sul dettaglio della telemetry esposta dalla specifica installazione.

## Camera Integration

### Sensori Camera Supportati

Cyberwave dichiara supporto a:

- USB webcams.
- IP cameras.
- Depth cameras.
- Infrared cameras.
- Industrial GigE cameras.
- RealSense e altri sensori RGB-D dove disponibili.

Il Python SDK consente di catturare frame come bytes, numpy, PIL o file path tramite `get_frame()`. Per camera depth, la stessa astrazione puo' esporre RGB, depth o altre modalita' se il driver e il sensore le supportano.

### Camera RGB Base: Logitech C270

Specifiche utili:

- Video HD 720p a 30 fps.
- Field of view dichiarato 55 gradi nelle pagine prodotto recenti; alcune pagine support citano 60 gradi.
- Microfono mono integrato con noise reduction, utile ma non centrale per questo MVP.
- USB 2.0, fixed focus, auto light correction.

Uso MVP:

- Baseline affidabile per P0.
- Buona per inquadratura fissa e props ad alto contrasto.
- Meno adatta a depth o stima distanza.

Fonti: [Logitech C270](https://www.logitech.com/en-us/shop/p/c270-hd-webcam), [Logitech C270 support specs](https://support.logi.com/hc/en-001/articles/360023462093-Logitech-HD-Webcam-C270-Technical-Specifications).

### Camera RGB-D: Intel RealSense D455

Specifiche utili:

- Stereo depth camera.
- Depth fino a 1280 x 720 e fino a 90 fps.
- RGB fino a 1280 x 800 o 1920 x 1080 secondo datasheet/famiglia.
- Range operativo indicativo 0.6-6 m; datasheet cita anche 0.4 m a oltre 6 m in base alle condizioni.
- IMU integrata per 6 DoF.
- Global shutter su depth e RGB nelle specifiche D455.

Uso MVP:

- Migliore opzione se serve distanza stimata del target.
- Utile per evitare che l'agente chieda al robot di avvicinarsi troppo.
- Non indispensabile per classificazione P0 se i props sono ben visibili.

Fonti: [Intel RealSense D455](https://www.intelrealsense.com/depth-camera-d455/), [Intel RealSense D455 product specs](https://www.intel.com/content/www/us/en/products/sku/205847/intel-realsense-depth-camera-d455/specifications.html).

Confidenza camera integration: alta sulle capacita' Cyberwave generali; media sulle modalita' disponibili per il sensore fisico in sede.

## Mapping Sensore -> Feature MVP

| Feature | Sensore minimo | Sensore migliore | Note |
| --- | --- | --- | --- |
| Classificazione `mine/non_mine/dubbio` | RGB camera | RGB + seconda vista | CV/VLM piu' importante del robot |
| Caso `dubbio` | Confidence bassa da RGB | Seconda camera/Go2/UGV pan-tilt | La feature premia interazione multi-robot |
| Distanza target | Stima visuale approssimata | RealSense depth o LiDAR | Non rendere P0 dipendente da depth |
| Navigazione breve | Teleop/controller policy | UGV camera + IMU o Go2 LiDAR | Sempre bounded e supervisionata |
| Safety stop | UI/manuale | UI + controller + fisico | Requisito indispensabile |
| Replay/demo review | Frame + log | Frame + telemetry + dataset | Utile per pitch finale |

## Raccomandazione Per La Demo

Priorita' sensori:

1. Camera fissa o UGV camera per P0.
2. UGV pan-tilt per mostrare sensing attivo.
3. Go2 camera per secondo punto di vista su `dubbio`.
4. Depth/LiDAR come arricchimento P1/P2, non dipendenza P0.
5. SO-101 solo dopo aver stabilizzato CV, UI e safety.

Setup consigliato:

- Preparare props ad alto contrasto e dimensioni simili.
- Delimitare una corsia per UGV/Go2.
- Tenere una camera fissa come fallback sempre pronta.
- Usare dry-run per tutte le azioni agentiche finche' la UI e il validatore non sono stabili.
- Tracciare nel log quale sensore ha generato ogni decisione.

## Checklist Di Verifica Hardware

- [ ] Elenco robot realmente disponibili e varianti esatte.
- [ ] Per ogni robot: twin Cyberwave online.
- [ ] Per ogni camera: latest-frame o stream accessibile.
- [ ] Controller policy e comandi disponibili.
- [ ] Area sicura per movimento bounded.
- [ ] Stop manuale e stop software verificati.
- [ ] Lighting e posizione props verificati.
- [ ] Fallback con immagini preregistrate pronto.

## Fonti Generali

- [Cyberwave Quickstart](https://docs.cyberwave.com/overview)
- [Cyberwave Python SDK repository](https://github.com/cyberwave-os/cyberwave-python)
- [Cyberwave Python SDK docs](https://docs.cyberwave.com/overview/tools/python-sdk.md)
- [Cyberwave Cameras overview](https://docs.cyberwave.com/overview/cameras.md)
- [Cyberwave UGV voice controlled tutorial](https://docs.cyberwave.com/tutorials/ugv-voice-controlled.md)
- [Cyberwave Go2 digital to physical tutorial](https://docs.cyberwave.com/tutorials/go2-digital-to-physical.md)
- [Cyberwave SO-101 natural language agent](https://docs.cyberwave.com/tutorials/so101-natural-language-agent.md)
- [Cyberwave SO-101 teleop dataset](https://docs.cyberwave.com/tutorials/so101-teleop-dataset.md)
- [Unitree Go2 official page](https://unitree-robot.com/go2/index.html)
- [Waveshare UGV Beast wiki](https://www.waveshare.com/wiki/UGV_Beast)
- [SO-101 specifications](https://www.roboticscenter.ai/hardware/so-101/specs)
- [Intel RealSense D455](https://www.intelrealsense.com/depth-camera-d455/)
- [Logitech C270](https://www.logitech.com/en-us/shop/p/c270-hd-webcam)
