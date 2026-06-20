---
name: webui keyboard shortcuts
overview: Aggiungere scorciatoie browser safety-first alla Web UI SafeGround, includendo WASD per movimento Go2 e una mappatura completa per stop, missione, runtime, marking, route planner, command palette e SO-101 takeover.
todos:
  - id: keyboard-composable
    content: Create a reusable frontend keyboard shortcut handler with editable-field guards and repeat prevention.
    status: pending
  - id: app-shortcut-actions
    content: Wire shortcuts in App.vue to existing movement, stop, mission, marking, command and route actions.
    status: pending
  - id: shortcut-ui
    content: Add Keyboard Drive controls, visual hints, and shortcut help overlay to the Web UI.
    status: pending
  - id: docs-shortcuts
    content: Document browser key mapping in README and docs/commands.md.
    status: pending
  - id: verify-shortcuts
    content: Run frontend build and backend tests, then manually verify browser shortcut behavior.
    status: pending
isProject: false
---

# Piano Shortcut Tastiera Web UI

## Obiettivo
Aggiungere una gestione keyboard-first pensata per demo fisica e browser: WASD per lo scout `go2`, stop prioritario, e comandi secondari coerenti con i pannelli già presenti.

## Stato Rilevato
- Movimento base già esiste in [`frontend/src/components/BaseMovementPanel.vue`](frontend/src/components/BaseMovementPanel.vue) e passa da `POST /api/robots/{robot_id}/move`.
- Safety già limita distanza/rotazione in [`safeground/models.py`](safeground/models.py): `distance_m <= 0.5`, `angle_degrees <= 15`, `operator_confirmed=true`.
- UI ha già mission start/stop, runtime, activation, camera marking, route planner, pickup workflow e SO-101 takeover in [`frontend/src/App.vue`](frontend/src/App.vue).
- Endpoint disponibili in [`safeground/api/server.py`](safeground/api/server.py): runtime, start/stop, mark observation, activation, movement, route plan, object pickup.

## UX Proposta
Implementare scorciatoie globali solo quando:
- l’utente non sta scrivendo in `input`, `textarea`, `select`, o contenteditable;
- la Web UI non è busy;
- per movimento, è attivo un toggle “Keyboard Drive” con target default `virtual` o `auto`.

Mappatura proposta:
- `W`: Go2 forward.
- `S`: Go2 backward.
- `A`: Go2 rotate left.
- `D`: Go2 rotate right.
- `Space`: Emergency Stop All, con `preventDefault` solo fuori dai campi testo.
- `Esc`: Emergency Stop All / clear keyboard drive focus.
- `F`: Start Field Scan.
- `Ctrl/Cmd+K`: focus Command Palette.
- `Ctrl/Cmd+Enter`: send Command Palette command quando il focus è nella palette.
- `M`: mark latest object as `MINE`.
- `N`: mark latest object as `NOT_MINE`.
- `U`: mark latest object as `UNCERTAIN`.
- `R`: plan currently drawn scout route, solo se il route planner ha almeno due waypoint.
- `C`: clear draft route, solo se il route planner è focused/hovered o Keyboard Drive è off.
- `H`: SO-101 hold position, solo con pannello SO-101 disponibile.
- `?`: open/close shortcut help overlay.

Eviterei shortcut globali per `live + dry_run=false`, arming fisico o replay pickup: restano azioni click-confirmed per ridurre rischio durante demo.

## Implementazione
1. Creare un composable in [`frontend/src/useKeyboardShortcuts.ts`](frontend/src/useKeyboardShortcuts.ts) per:
   - registrare `keydown`/`keyup` su `window`;
   - ignorare eventi quando il target è editabile;
   - normalizzare `key`, modifier e repeat;
   - gestire `preventDefault` solo per shortcut gestite.
2. Estendere [`frontend/src/App.vue`](frontend/src/App.vue):
   - aggiungere stato `keyboardDriveEnabled`, `shortcutHelpOpen`, ultimo shortcut eseguito;
   - collegare callback a funzioni esistenti: `runBaseMovement`, `runAction(stopMission)`, `startMission`, `markCameraObject`, `planScoutRoute`;
   - mantenere `WASD` su `go2` con `movement_target` coerente al pannello, default `virtual`.
3. Aggiornare [`frontend/src/components/BaseMovementPanel.vue`](frontend/src/components/BaseMovementPanel.vue):
   - mostrare toggle `Keyboard Drive`;
   - mostrare tasti WASD nel pannello movimento;
   - riusare distanza/angolo selezionati anche per shortcut.
4. Aggiornare [`frontend/src/components/ScoutPathPlanner.vue`](frontend/src/components/ScoutPathPlanner.vue):
   - esporre `clear` e `submit` controllabili da parent, oppure gestire stato draft nel parent se più semplice;
   - mostrare hint `R` plan e `C` clear.
5. Aggiungere [`frontend/src/components/KeyboardShortcutsOverlay.vue`](frontend/src/components/KeyboardShortcutsOverlay.vue):
   - help overlay apribile con `?`;
   - raggruppare shortcut per Safety, Movement, Mission, Perception, Route, SO-101.
6. Aggiornare docs:
   - [`docs/commands.md`](docs/commands.md) con sezione “Web UI Keyboard Shortcuts”;
   - [`README.md`](README.md) con quick reference breve.

## Verifica
- Eseguire `cd frontend && npm run build`.
- Eseguire `.venv/bin/python -m unittest discover -s tests` per assicurare che non si rompa backend/API.
- Test manuale browser:
  - `?` apre help;
  - WASD non funziona mentre si scrive nella Command Palette;
  - `Space`/`Esc` invocano Stop All;
  - `WASD` invia solo micro-movimenti bounded e auditati;
  - `M/N/U` marcano solo se esiste una latest observation;
  - shortcut fisici restano bloccati se non sono soddisfatte runtime/live/armed safety.