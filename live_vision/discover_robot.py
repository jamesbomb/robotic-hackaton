#!/usr/bin/env python3
"""
discover_robot.py — scopri-robot: cosa espone DAVVERO il robot/twin Cyberwave SUL POSTO.

Mentore: "non assumere i nomi — leggi cosa espone davvero". L'introspezione dell'SDK
ha detto che le azioni sono MOVIMENTI NOMINATI (run_movement/move_to_pose) + comandi
bassi (publish_command). Questo script, connesso al robot vero, dump:
  - twin.describe()                  → cos'è il twin
  - twin.list_movements()            → i NOMI reali (qui scopri come si chiama "pick", "home"…)
  - twin.get_controllable_joint_names() → i giunti del braccio
  - has_capability(...)              → cosa sa fare (camera, arm, nav…)
Da qui sai con cosa wirare robot.py (pick/navigate ai nomi VERI).

Config via env (o passa --asset / --env):
  CYBERWAVE_API_KEY / CYBERWAVE_TOKEN, CYBERWAVE_BASE_URL (default cloud),
  CYBERWAVE_ENV (environment_id), CYBERWAVE_ASSET (asset_key del cane),
  CYBERWAVE_MQTT_HOST (edge node hackathon).

Uso:  python discover_robot.py --asset <asset_key>
"""
import os, sys, json, cyberwave

def arg(flag, env, default=None):
    if flag in sys.argv: return sys.argv[sys.argv.index(flag) + 1]
    return os.environ.get(env, default)

ASSET = arg("--asset", "CYBERWAVE_ASSET")
ENVID = arg("--env", "CYBERWAVE_ENV")
BASE  = arg("--base", "CYBERWAVE_BASE_URL", "https://api.cyberwave.com")

cyberwave.configure(
    base_url=BASE,
    api_key=os.environ.get("CYBERWAVE_API_KEY"),
    token=os.environ.get("CYBERWAVE_TOKEN"),
    environment=ENVID,
    mqtt_host=os.environ.get("CYBERWAVE_MQTT_HOST"),
)
client = cyberwave.get_client()
print(f"[ok] client · base={BASE} · env={ENVID} · asset={ASSET}")

try:
    twin = client.twin(asset_key=ASSET, environment_id=ENVID)
    print(f"[ok] twin uuid = {getattr(twin,'uuid', '?')}")
except Exception as e:
    print(f"[!] twin(asset_key={ASSET}) fallito: {e}\n    → verifica CYBERWAVE_ASSET / connessione edge.")
    sys.exit(1)

def show(label, fn):
    print(f"\n═══ {label} ═══")
    try:
        out = fn()
        print(json.dumps(out, indent=2, default=str)[:2500] if not isinstance(out, str) else out)
    except Exception as e:
        print(f"  (non disponibile: {e})")

show("describe()", twin.describe)
show("list_movements()  ← I NOMI VERI per pick/home/ecc", lambda: twin.list_movements())
show("get_controllable_joint_names()  ← giunti braccio", twin.get_controllable_joint_names)
print("\n═══ capabilities ═══")
for cap in ("camera", "arm", "manipulator", "navigation", "move", "pick", "gripper", "lidar", "depth"):
    try: print(f"  has_capability({cap!r}) = {twin.has_capability(cap)}")
    except Exception as e: print(f"  has_capability({cap!r}) → {e}")

print("\n→ Annota i NOMI dei movimenti (pick/home/…) e i comandi nav: vanno in robot.py")
