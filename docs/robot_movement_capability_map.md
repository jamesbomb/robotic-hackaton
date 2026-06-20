# SafeGround Robot Movement Capability Map

## Scopo

Questa mappa raccoglie i movimenti disponibili o documentati per Unitree Go2,
SO-101 e UGV Beast, distinguendo:

- cosa e' gia' integrato nel codice SafeGround;
- cosa e' documentato da Cyberwave o dal produttore;
- cosa richiede validazione onsite;
- cosa deve restare fuori dalla demo per motivi di safety.

Regola generale: "possibile" non significa "abilitato". Ogni movimento fisico
deve passare da allow-list, conferma operatore, timeout, stop e area libera.

## Stato Attuale SafeGround

| Robot | Integrato nel codice | Endpoint/UI | Stato |
| --- | --- | --- | --- |
| Go2 | `move_forward`, `move_backward`, `rotate_left`, `rotate_right`, route plan mock | `POST /api/robots/go2/move`, `POST /api/robots/go2/route-plan`, pannello Base Movement | Mock/simulation contract; live adapter non cablato |
| UGV Beast | stessi comandi base mock se esposti dall'adapter | `POST /api/robots/{robot_id}/move` | Mock/simulation contract; driver Cyberwave/ROS2 non cablato |
| SO-101 | `home`, `hold_position`, `nudge_joint`, `place_safe_marker` | `POST /api/robots/so101/manual-arm`, pannello SO-101 Takeover | Mock-safe; joint live adapter non cablato |

## Unitree Go2

### Movimenti SafeGround P0

| Capacita | Comando SafeGround | Limite P0 | Note |
| --- | --- | --- | --- |
| Avanti breve | `move_forward` | max 0.5 m | Stop prima/dopo |
| Indietro breve | `move_backward` | max 0.5 m | Stop prima/dopo |
| Ruota sinistra | `rotate_left` | max 15 deg | Stop prima/dopo |
| Ruota destra | `rotate_right` | max 15 deg | Stop prima/dopo |
| Stop | `stop` / `Stop All` | immediato | Deve restare sempre disponibile |
| Route/waypoints demo | `route-plan` mock | punti su mappa UI | Non e' ancora Nav2 live |

### Cyberwave / ROS2

| Capacita | API/documentazione | Uso SafeGround |
| --- | --- | --- |
| Locomozione helper | `move_forward(distance)`, `move_backward(distance)`, `turn_left(angle)`, `turn_right(angle)` | Da cablare in adapter Cyberwave |
| Modalita runtime | `cw.affect("simulation")`, `cw.affect("live")` | Gia' selezionabile da UI, ma adapter live non cablato |
| Navigazione autonoma | driver ROS2 Go2 + Nav2/SLAM/elevation mapping | P1/P2, solo dopo mappa e safety rehearsal |
| Velocity commands con obstacle avoidance | Go2 ROS2 driver, obstacle avoidance onboard + driver-level | Non P0 live; possibile teleop mapping supervisionato |
| Sensori per navigazione | `/odom`, `/point_cloud2`, `/scan`, `/camera/image_raw`, `/joint_states`, `/imu/data`, `/map` | Da leggere per capability map reale |

### Unitree Sport API

| Categoria | Azioni documentate | Decisione SafeGround |
| --- | --- | --- |
| Stato/postura base | `Damp`, `BalanceStand`, `StopMove`, `StandUp`, `StandDown`, `RecoveryStand`, `Sit`, `RiseSit` | Candidati adapter live, con conferma operatore |
| Movimento continuo | `Move(vx, vy, vyaw)`, `Euler(roll, pitch, yaw)`, `SpeedLevel` | Non esporre raw in UI; wrappare in micro-comandi bounded |
| Gait | `StaticWalk`, `TrotRun`, `EconomicGait`, `ClassicWalk`, `FreeWalk`, `FreeBound`, `FreeJump`, `FreeAvoid`, `CrossStep` | Da validare; non P0 |
| Joystick/avoidance | `SwitchJoystick`, `SwitchAvoidMode`, auto-recovery set/get | Solo setup/teleop supervisionata |
| Gesture/trick | `Hello`, `Stretch`, `Dance1`, `Dance2`, `Heart`, `Pose`, `Scrape` | Fuori P0; evitare in area demo affollata |
| Acrobatiche | `FrontFlip`, `FrontJump`, `FrontPounce`, `LeftFlip`, `BackFlip`, `HandStand`, `WalkUpright` | Vietate nella demo SafeGround |

### Da Validare Onsite

- Variante: Air, Pro, X, EDU.
- Firmware e AES key se firmware >= 1.1.15.
- Controller policy Cyberwave effettivamente assegnata.
- Se il twin espone helper locomotion, Nav2 task o solo teleop.
- Stop fisico, `StopMove`, latenza e comportamento obstacle avoidance.

## UGV Beast

### Movimenti SafeGround P0

| Capacita | Comando SafeGround | Limite P0 | Note |
| --- | --- | --- | --- |
| Avanti breve | `move_forward` | max 0.5 m | Mock/simulation, live da cablare |
| Indietro breve | `move_backward` | max 0.5 m | Mock/simulation, live da cablare |
| Ruota sinistra | `rotate_left` | max 15 deg | Mock/simulation, live da cablare |
| Ruota destra | `rotate_right` | max 15 deg | Mock/simulation, live da cablare |
| Stop | `stop` / `Stop All` | immediato | Requisito P0 |

### Waveshare / ROS2

| Capacita | API/documentazione | Uso SafeGround |
| --- | --- | --- |
| Avanti a distanza | ROS2 behavior `drive_on_heading`, data in metri | Cablare come `move_forward` |
| Indietro a distanza | ROS2 behavior `back_up`, data in metri | Cablare come `move_backward` |
| Rotazione | ROS2 behavior `spin`, data in gradi; positivo sinistra, negativo destra | Cablare come `rotate_left/right` |
| Stop | ROS2 behavior `stop` | Cablare a `Stop All` |
| Salva punto mappa | ROS2 behavior `save_map_point`, data `a`-`g` | P1/P2 dopo mappa |
| Vai a punto mappa | ROS2 behavior `pub_nav_point`, data `a`-`g` | P1/P2 con Nav2 |
| Velocita ruote closed-loop | JSON `{"T":1,"L":...,"R":...}` | Non esporre raw; usare wrapper bounded |
| PWM ruote open-loop | JSON `{"T":11,"L":...,"R":...}` | Vietato per SafeGround demo |
| ROS velocity | JSON `{"T":13,"X":...,"Z":...}` | Solo adapter interno con limiti |
| Pan-tilt assoluto | JSON `{"T":133,"X":...,"Y":...,"SPD":...,"ACC":...}` | Utile per second look senza muovere base |
| Pan-tilt continuo | JSON `{"T":134,...}` o UI `{"T":141,...}` | Solo bounded/supervisionato |
| Pan-tilt stop | JSON `{"T":135}` | Da cablare se pan-tilt usato |

### Da Validare Onsite

- Variante Pi/Jetson e workspace ROS2 reale.
- Se Cyberwave UGV espone direttamente `relative_move`, `rotate`, waypoint o solo bridge custom.
- Odometria affidabile per `drive_on_heading`, `back_up`, `spin`.
- Pan-tilt installato e range reale.
- Stop software e stop fisico.

## SO-101

### Movimenti SafeGround P0/P2

| Capacita | Comando SafeGround | Limite | Note |
| --- | --- | --- | --- |
| Home | `home` | posa zero/prevalidata | Sempre preferire ritorno home |
| Hold | `hold_position` | nessun movimento | Per takeover umano |
| Nudge giunto | `nudge_joint` | max +/-5 deg | Solo giunti allow-listati |
| Marker sicuro | `place_safe_marker` | solo `NOT_MINE` | Posa prevalidata fuori zona rischio |

### Cyberwave / SO-101

| Capacita | API/documentazione | Uso SafeGround |
| --- | --- | --- |
| Lista giunti | `robot.joints.list()` | Prima azione live obbligatoria |
| Stato giunti | `robot.joints.get()`, `get_all()`, `print_joint_states()` | Telemetria e debug |
| Set singolo giunto | `robot.joints.set(name, value, degrees=True)` | Cablare dietro `nudge_joint` |
| Set multi-giunto / pose | `joints.set({...})` o executor con `set_pose` | Cablare solo con pose prevalidate |
| Ramping/smooth motion | MotionExecutor: interpolazione a 20 Hz | Necessario per live, evitare step bruschi |
| Wait | motion plan `wait` | Utile tra sequenze |
| Teleop leader/follower | Local Teleop | Setup/dataset, non controllo autonomo SafeGround |
| Keyboard remote operation | Dashboard Keyboard controller | Smoke test prima di SDK |
| VLA/controller policy | Assign Controller Policy | P2+; non usare su target sospetti |

### Nomi Giunti Da Mappare

| Fonte | Nomi/ID |
| --- | --- |
| Cyberwave NL arm controller | `"1"` base rotation, `"2"` shoulder pitch, `"3"` elbow, `"4"` wrist pitch, `"5"` wrist roll, `"6"` gripper/wrist yaw |
| LeRobot/SO-101 | `shoulder_pan`, `shoulder_lift`, `elbow_flex`, `wrist_flex`, `wrist_roll`, `gripper` |
| SafeGround mock attuale | `base`, `shoulder`, `elbow`, `wrist_pitch`, `wrist_roll`, `gripper` |

Prima del live, normalizzare i nomi usando `arm.joints.list()` sull'istanza reale
e aggiornare l'allow-list SafeGround. Non assumere che nomi LeRobot e nomi
Cyberwave coincidano.

### Da Validare Onsite

- Calibrazione verde nel dashboard.
- Driver `so101-remoteoperate` attivo.
- Keyboard controller muove ogni giunto.
- Script minimo `joints.set("1", 10, degrees=True)` o nome reale equivalente.
- Range gripper e payload marker.
- Collision detection e workspace libero.

## Decisione Safety Per La Demo

| Livello | Consentito |
| --- | --- |
| P0 mock/simulation | micro-movimenti base, SO-101 home/hold/nudge/marker mock |
| P0 live smoke | un micro-movimento mobile o un nudge SO-101, con operatore e stop testato |
| P1/P2 | waypoint/route, pan-tilt, marker fisico su area sicura, raccolta oggetto assistita record/replay |
| Vietato | Go2 acrobazie, velocity raw continuo da UI/LLM, PWM raw UGV, SO-101 su `MINE` o `UNCERTAIN` |

## Movimento Composto: Raccolta Oggetto Assistita

Sequenza SafeGround:

1. Go2 entra in postura bassa (`stand_down` / low posture) come step prevalidato.
2. La UI apre il workflow `Object Pickup` e associa i feed video disponibili.
3. L'operatore controlla SO-101 con comandi bounded (`home`, `hold_position`, `nudge_joint`, `place_safe_marker` se `NOT_MINE`).
4. Ogni comando SO-101 viene registrato come step del template, insieme ai riferimenti video.
5. Il template puo' essere riusato dalla UI; in questa fase il replay e' auditable ma non esegue ancora presa autonoma.
6. In seconda fase, YOLO puo' proporre gli stessi step solo dopo validazione safety e conferma operatore.

## Fonti

- Cyberwave Python SDK: https://docs.cyberwave.com/overview/tools/python-sdk
- Cyberwave Go2 digital-to-physical: https://docs.cyberwave.com/tutorials/go2-digital-to-physical
- Cyberwave Go2 ROS2 driver: https://docs.cyberwave.com/api-reference/autonomous-navigation-driver.md
- Cyberwave SO-101 natural language agent: https://docs.cyberwave.com/tutorials/so101-natural-language-agent
- Cyberwave SO-101 teleop dataset: https://docs.cyberwave.com/tutorials/so101-teleop-dataset
- Cyberwave Python SDK package notes: https://pypi.org/project/cyberwave/0.5.0/
- Unitree Go2 product page: https://unitree-robot.com/go2/index.html
- Unitree SDK2 Go2 Sport API header: https://raw.githubusercontent.com/unitreerobotics/unitree_sdk2/008157a4/include/unitree/robot/go2/sport/sport_api.hpp
- Unitree SDK2 Go2 sport client example: https://raw.githubusercontent.com/unitreerobotics/unitree_sdk2/c55e8558/example/go2/go2_sport_client.cpp
- Waveshare UGV Beast wiki: https://www.waveshare.com/wiki/UGV_Beast
- Waveshare UGV Beast ROS2 command interaction: https://www.waveshare.com/wiki/UGV_Beast_PI_ROS2_10._Command_interaction
- Waveshare JSON instruction set: https://www.waveshare.com/wiki/08_Slave_Device_JSON_Instruction_Set
- Robotics Center SO-101 specs: https://www.roboticscenter.ai/hardware/so-101/specs
- Hugging Face / LeRobot SO-101: https://huggingface.co/docs/lerobot/en/so101
