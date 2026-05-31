# Spike-Findings (Phase 0) — AUTORITATIV

Quelle: Live-Tests gegen `https://navimow-fra.ninebot.com` (Token aus der laufenden
offiziellen Integration) **+** Open-Source-SDK `segwaynavimow/navimow-sdk`
(`mower_sdk/api.py`, `models.py`) als maßgebliche Referenz für Payloads/Enums.

> Geräte-ID wird zur Laufzeit aus `authList` geholt; sie steht bewusst NICHT in diesem Repo.

---

## 1. Envelope (alle smarthome-Endpunkte)

```json
{ "code": 1, "desc": "Operation successful",
  "data": { "requestId": "...", "payload": { ... } } }
```
- **Erfolg = `code == 1`** (NICHT 0/200!).
- Nutzdaten liegen unter `data.payload`.
- Header je Request: `Authorization: Bearer <token>`, `requestId: <uuid4>`, `Content-Type: application/json`.

## 2. authList

- `GET /openapi/smarthome/authList` (kein Body).
- Geräte: `data.payload.devices[]`, je Gerät: `{ "id", "name", "model", "firmware" }`.
- Geräte-Identifikator-Feld: **`id`** (z.B. Modell `i105`, firmware `005E`).

## 3. getVehicleStatus

- `POST /openapi/smarthome/getVehicleStatus`
- Body: **`{ "devices": [ { "id": "<id>" } ] }`** (Liste von Objekten).
- Antwort: `data.payload.devices[]`, je Gerät:
  ```json
  { "id": "<id>",
    "vehicleState": "isDocked",
    "capacityRemaining": [ { "unit": "PERCENTAGE", "rawValue": 36 } ],
    "descriptiveCapacityRemaining": "MEDIUM" }
  ```
- Akku: `capacityRemaining[]` mit `unit=="PERCENTAGE"` → `rawValue` (Fallback: erstes Item).

## 4. vehicleState-Enum → LawnMowerActivity

Vollständig aus `mower_sdk/models.py` `_RAW_STATE_TO_CANONICAL` (autoritativer als physisches Testen):

| Cloud `vehicleState` | kanonisch | LawnMowerActivity |
|---|---|---|
| `isDocked` | docked | DOCKED |
| `isIdle`, `isIdel` | idle | DOCKED |
| `Self-Checking`, `Self-checking` | idle | DOCKED |
| `isMapping`, `isRunning` | mowing | **MOWING** |
| `isPaused`, `inSoftwareUpdate` | paused | PAUSED |
| `isDocking` | returning | **RETURNING** |
| `Error`, `error`, `isLifted` | error | ERROR |
| `Offline`, `offline` | unknown | ERROR (oder None) |
| (unbekannt) | — | ERROR (Default) |

## 5. sendCommands — Google-Smart-Home-Grammatik

- `POST /openapi/smarthome/sendCommands`
- Body:
  ```json
  { "commands": [ {
      "devices": [ { "id": "<id>" } ],
      "execution": { "command": "<cmd>", "params": { ... } }
  } ] }
  ```
- Befehls-Mapping (`mower_sdk/api.py`):

| Aktion | `command` | `params` |
|---|---|---|
| Start | `action.devices.commands.StartStop` | `{ "on": true }` |
| Stop | `action.devices.commands.StartStop` | `{ "on": false }` |
| Pause | `action.devices.commands.PauseUnpause` | `{ "on": false }` |
| Resume | `action.devices.commands.PauseUnpause` | `{ "on": true }` |
| Dock | `action.devices.commands.Dock` | (keine) |

- Antwort: `data.payload.commands[]`, je Eintrag `status` (`ERROR` + `errorCode`).
  `errorCode == "alreadyInState"` → als Erfolg behandeln (idempotent).

## 6. Auth — DER Kernbefund

Token-Dict der offiziellen Integration (Werte redacted):
```
access_token  = <32 Zeichen>
refresh_token = <32 Zeichen>     ← EXISTIERT (entgegen NavimowHA-Annahme)
token_type    = Bearer
expires_in    = 3600             ← Token lebt nur 1 STUNDE
code=4003, desc=TOKEN_EMPTY      ← Fehler-Response in den Token gemergt (Bug)
```

- **Refresh-Endpoint:** `POST /openapi/oauth/getAccessToken`, `Content-Type: application/x-www-form-urlencoded`,
  Body: `grant_type=refresh_token & refresh_token=<rt> & client_id=homeassistant & client_secret=57056e15-722e-42be-bbaa-b0cbfb208a52`.
- **Antwort ist Standard-OAuth2-JSON** (KEIN `{code,data}`-Envelope):
  ```json
  { "access_token":"...", "refresh_token":"...", "token_type":"Bearer", "expires_in":3600 }
  ```
- **Der `refresh_token` ROTIERT** bei jedem Refresh → neuer RT muss persistiert werden.

### Ursache der Instabilität (bewiesen)
Token 1 h gültig → stündlicher Refresh nötig. In NavimowHA refreshen **MQTT-Disconnect-Pfad und
Coordinator gleichzeitig** → erster rotiert den RT, zweiter nutzt den alten (jetzt ungültigen) →
`4003/TOKEN_EMPTY` → in den Token gemergt → kaputt bis Neustart (Neustart liest den noch gültigen
access_token erneut).

### Lösung (unser Design)
- **Ein** TokenManager als einziger Token-Besitzer, **`asyncio.Lock`** → nie zwei parallele Refreshes.
- **Kein MQTT** → kein zweiter Refresh-Pfad.
- Rotierten `refresh_token` immer speichern; Refresh-Antwort als Standard-OAuth2-JSON parsen;
  bei Fehler NIE die Fehler-Response in den Token mergen.
- Initialen Token via **Browser-OAuth (Weg B)** wie NavimowHA (bewährt) → danach stündlicher,
  serialisierter Refresh → **unbeaufsichtigt**. Email+PW-Reverse-Engineering (Weg A) NICHT nötig.

---

## 7. Auswirkungen auf bereits gebauten Code (vor Spike)

- `const.py`: `STATE_MAP` (war geraten, jetzt echte Strings), `COMMANDS` (Google-Grammatik),
  `DEVICE_SN_KEY` entfällt (Key ist `id`, Body ist Objekt-Liste), Erfolg `code==1`.
- `api.py`: Envelope-Parsing (`code==1`, `data.payload.devices`), `get_status`-Body
  `{"devices":[{"id":...}]}`, `send_command` baut `commands[].execution`-Struktur + prüft
  `payload.commands[].status`.
- `auth.py`-Kern (Lock/Expiry) bleibt gültig; Refresh-Callback (form-encoded, RT-Rotation,
  Persistenz) kommt in Task 11.
- `config_flow`/`__init__`: **Weg B (Browser-OAuth)** statt Email+PW.
