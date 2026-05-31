# Design: `navimow_simple` — schlanke Navimow-i105-Integration für Home Assistant

**Datum:** 2026-05-31
**Status:** Design (zur Review)
**Domain:** `navimow_simple`
**Repo:** `navimow-i105-ha`
**Lizenz:** GPL-3.0 (abgeleitet von `segwaynavimow/NavimowHA`)

---

## 1. Ziel & Motivation

Eine eigene, schlanke HA-Custom-Integration für den **Segway Navimow i105 (H-Serie)**,
(Geräte-ID lokal/privat, nicht im Repo). Sie ersetzt für den Eigenbedarf die offizielle Integration,
deren Status durch MQTT-Komplexität und stündlichen HTTP-Fallback oft veraltet bzw.
instabil ist.

**Kernprinzip:** *Ein Token-Besitzer, ein Kanal (HTTP-Polling), null MQTT.*

### Diagnose der Instabilität (aus Analyse von NavimowHA)

Zwei unabhängige Ursachen, die wir gezielt eliminieren:

1. **Laufzeit-Zustand-Korruption (häufige Abbrüche, durch Neustart behebbar).**
   NavimowHA verbindet MQTT als Primärkanal. Der Broker trennt die Verbindung
   stündlich; der Disconnect-Callback (`_async_refresh_mqtt_credentials`,
   `__init__.py` Z. 261-313) holt dann OAuth-Token **und** MQTT-Credentials neu.
   Diese MQTT-getriebenen Refreshes konkurrieren mit den Coordinator-Refreshes →
   `api._token` / MQTT-Credentials desynchronisieren im Speicher → `CODE_OAUTH_INFO_ILLEGAL`.
   **Beleg:** Ein Neustart der offiziellen Integration behebt das Problem *immer* —
   d.h. der gespeicherte Token ist nicht abgelaufen, nur der In-Memory-Zustand verrottet.
   → **Lösung: MQTT komplett entfernen.** Kein Pfad mehr, der Zustand korrumpiert.

2. **Echter Token-Ablauf (selten, alle ~1-2 Tage).**
   Der initiale Token von `getAccessToken` enthält **keinen `refresh_token`**
   (`auth.py` Z. 59-64, `OAUTH2_REFRESH = None`). Nach Ablauf ist ein neuer Login nötig.
   → **Lösung: Spike klärt, ob ein stiller E-Mail+PW-Re-Login möglich ist; sonst sauberer
   Browser-OAuth-Reauth-Flow.** (Komfort, nicht stabilitätskritisch.)

---

## 2. Architekturentscheidungen (getroffen)

| Entscheidung | Wahl | Begründung |
|---|---|---|
| Entity-Modell | `lawn_mower`-Plattform + Sensoren | Native HA-Plattform, exakt Start/Pause/Dock |
| Code-Strategie | Cleaner Neuaufbau, OAuth-Ideen portiert | Kein MQTT-Ballast, volle Kontrolle |
| Repo | Eigenes, standalone (`navimow-i105-ha`) | Saubere Trennung von `weather_mow` |
| Geräte-Umfang | Nur ein i105 (YAGNI) | Kein Multi-Device-Handling |
| Polling-Intervall | **90 s** | Mitte aus Aktualität & API-Schonung |
| Token-Strategie | **Spike zuerst**, dann still oder Browser | Faktenbasiert statt Annahme |
| Resume | `START_MOWING` kontextabhängig = Resume | Bleibt nativ, kein Extra-Button |
| MQTT | Komplett entfernt | Hauptquelle der Instabilität |

### Ziel-Qualitätsstufe
**Bronze → Silver** der HA Integration Quality Scale. Silver-relevant und von Anfang an
eingeplant: `reauthentication-flow`, `config-entry-unloading`, `entity-unavailable`,
`parallel-updates` (`PARALLEL_UPDATES`), `test-coverage ≥95%`.

---

## 3. Ziel-API (smarthome-openapi, live bestätigt)

Basis: `https://navimow-fra.ninebot.com`

| Zweck | Methode / Pfad | Notizen |
|---|---|---|
| Geräteliste | `GET /openapi/smarthome/authList` | liefert die Geräte-ID (zur Laufzeit) |
| Status | `POST /openapi/smarthome/getVehicleStatus` | `vehicleState`, `capacityRemaining` |
| Steuern | `POST /openapi/smarthome/sendCommands` | Start / Pause / Dock |
| Token | `POST /openapi/oauth/getAccessToken` | Client-ID `homeassistant`, Secret öffentlich |

**Header je Request:** `Authorization: Bearer {access_token}`, `requestId: {uuid4}`.

> Diese smarthome-openapi ist **einfacher** als die von NavimowHAs `mower_sdk` genutzte API.
> Wir bauen den HTTP-Client direkt darauf — **kein `mower_sdk`-Dependency**.

Status-Beispiel (live):
```json
{"vehicleState": "isDocked",
 "capacityRemaining": [{"unit": "PERCENTAGE", "rawValue": 100}],
 "descriptiveCapacityRemaining": "FULL"}
```

---

## 4. Phase 0 — Spike (erster Schritt, eigener Branch, Wegwerf-Code)

Skript `scripts/spike_auth.py` (HA-unabhängig) klärt **drei** Fakten vor dem echten Bau.
Nutzer wirkt mit (löst Mäher-Zustände aus, schneidet Login-Request mit).

1. **Stiller Login (Komfort-Bonus):** Was sendet die H5-Seite / App bei E-Mail+PW an
   `getAccessToken`? Gibt es `grant_type=password`? Enthält die Antwort einen
   `refresh_token` oder nur kurzlebigen `access_token`?
   → entscheidet **Weg A (still)** vs. **Weg B (Browser-OAuth)**.
2. **`vehicleState`-Enum (build-kritisch):** Exakte Strings für
   docked / mowing / paused / returning / error. Nutzer löst Zustände am i105 aus.
3. **`sendCommands`-Payload (build-kritisch):** Genaues JSON-Schema für Start/Pause/Dock.

**Decision-Gate:** Ergebnis legt `auth.py`- und `const.py`-Mapping fest. Erst danach Phase 1.
Fällt der stille Login durch → Browser-OAuth-Fallback, ohne Blocker.

---

## 5. Dateistruktur (Phase 1+)

```
navimow-i105-ha/
├── custom_components/navimow_simple/
│   ├── __init__.py          # async_setup_entry/unload — schlank, kein MQTT, runtime_data
│   ├── const.py             # Domain, URLs, Client-ID/Secret, Intervall, State-Mapping
│   ├── auth.py              # TokenManager: EIN Token, Refresh-Lock, Re-Auth
│   ├── api.py               # NavimowClient: 3 HTTP-Calls, HA-unabhängig, unit-testbar
│   ├── coordinator.py       # DataUpdateCoordinator (90s), einziger Token-Nutzer
│   ├── config_flow.py       # Setup + Reauth (Formvariante je nach Spike)
│   ├── lawn_mower.py        # LawnMowerEntity (START/PAUSE/DOCK, Start=Resume)
│   ├── sensor.py            # Akku-% (device_class battery) + Status-Text
│   ├── diagnostics.py       # Redacted JSON-Snapshot
│   ├── manifest.json        # iot_class: cloud_polling
│   ├── strings.json
│   └── translations/{de,en}.json
├── tests/                   # pytest; api.py + Mapping voll unit-getestet
├── scripts/spike_auth.py    # Phase-0-Wegwerf-Skript
├── hacs.json
├── README.md                # inkl. Attribution an NavimowHA (GPL)
├── LICENSE                  # GPL-3.0
├── pyproject.toml           # uv + ruff + ty, version == manifest
├── uv.lock
└── .github/workflows/ci.yml # HACS-Validierung, hassfest, ruff, pytest
```

---

## 6. Komponenten-Design

### 6.1 `auth.py` — TokenManager (das Herz)

Einzige Stelle, die Tokens anfasst.

- Speichert `access_token` + `expires_at` im Config-Entry (HA-verschlüsselt).
- `async_get_valid_token()` läuft hinter **einem `asyncio.Lock`** → verhindert parallele
  Refreshes (die 4003-Verschmutzung). Ablaufprüfung mit Sicherheitspuffer (~60 s vor `expires_at`).
- Bei echtem Ablauf:
  - **Weg A (still):** Re-Login mit gespeicherter E-Mail+PW → neuer Token, transparent.
  - **Weg B (Browser):** `raise ConfigEntryAuthFailed` → HA-Reauth-Flow.
- Bei `4003` / `TOKEN_EMPTY` aus einem API-Call: Token einmal invalidieren + neu holen,
  Call **genau einmal** wiederholen. Schlägt das fehl → `ConfigEntryAuthFailed`.

### 6.2 `api.py` — NavimowClient (HA-unabhängig)

- Konstruktor nimmt `aiohttp.ClientSession` + `TokenManager` (Websession injizierbar → Platinum-ready).
- Methoden: `async_get_devices()`, `async_get_status(device_id)`, `async_send_command(device_id, command)`.
- Setzt Header (`Bearer`, `requestId=uuid4`) je Request.
- Übersetzt API-Fehlercodes (`4003` etc.) in typisierte Exceptions (`NavimowAuthError`, `NavimowApiError`).
- **Keine HA-Imports** → reine pytest-Unit-Tests mit gemocktem aiohttp.

### 6.3 `coordinator.py`

- `DataUpdateCoordinator[dict]`, `update_interval = 90 s`.
- `_async_update_data`: proaktiv `token_manager.async_get_valid_token()` → `api.async_get_status()`
  → `{"state": <vehicleState>, "battery": <pct>, "raw": <response>}`.
- `entity-unavailable` / `log-when-unavailable`: bei API-Fehler Daten als veraltet markieren,
  Zustandswechsel (nicht jeden Poll) loggen.
- `PARALLEL_UPDATES = 1`.

### 6.4 `lawn_mower.py`

- `LawnMowerEntity`, Features `START_MOWING | PAUSE | DOCK`.
- `activity`: mappt `vehicleState` → `LawnMowerActivity`
  (DOCKED / MOWING / PAUSED / RETURNING / ERROR; exakte Strings aus Spike).
- `async_start_mowing`: kontextabhängig — aus PAUSED = Resume-Befehl, sonst Start.
- Nach jedem Command sofort `coordinator.async_request_refresh()` → schnelles UI-Feedback.
- `has_entity_name = True`, stabile `unique_id`, gemeinsames `DeviceInfo` (S/N = Geräte-ID).

### 6.5 `sensor.py`

- **Akku-%**: `device_class = battery`, `native_unit = %`, aus `capacityRemaining[0].rawValue`.
- **Status-Text**: roher `vehicleState` als String (für Automationen & Verlauf).
- Beide dünne `CoordinatorEntity`-Wrapper.

### 6.6 `config_flow.py`

- **Setup**: Formvariante je nach Spike-Ergebnis —
  Weg A: E-Mail + Passwort; Weg B: Browser-OAuth (`AbstractOAuth2FlowHandler`).
- `test-before-configure`: Login + `authList` während Setup validieren.
- `unique-config-entry`: `unique_id` = Geräte-ID, Doppel-Setup verhindern.
- **Reauth-Flow** (`async_step_reauth` / `_confirm`): Silver-Pflicht. Bei Weg A still mit
  gespeicherten Credentials; bei Weg B Browser-Login erneut.

### 6.7 `diagnostics.py`

- Redacted JSON-Snapshot: Geräteinfo, letzter Status, Token-Metadaten (Token selbst **redacted**),
  Coordinator-Meta (letzte Update-Zeit, Fehlerzähler).

---

## 7. Fehlerbehandlung & Token-Lifecycle (Zusammenfassung)

| Situation | Verhalten |
|---|---|
| Paralleler Token-Zugriff | `asyncio.Lock` im TokenManager → genau ein Refresh |
| Token kurz vor Ablauf | proaktiver Refresh mit 60-s-Puffer beim Poll |
| `4003` / `TOKEN_EMPTY` bei Call | invalidieren → neu holen → 1× Retry → sonst `ConfigEntryAuthFailed` |
| Echter Ablauf, Weg A | stiller Re-Login mit gespeicherten Credentials |
| Echter Ablauf, Weg B | `ConfigEntryAuthFailed` → HA-Reauth-Flow |
| Transienter Netzfehler | Daten veraltet markieren, nicht re-authen, nächster Poll |
| Command schlägt fehl | `HomeAssistantError` mit Klartext (`action-exceptions`) |

---

## 8. Tests

- **Unit (kein HA):** `api.py` (aiohttp gemockt) — alle Endpunkte, Fehlercodes, Retry-Logik;
  `vehicleState`→`LawnMowerActivity`-Mapping.
- **HA-Integration:** `pytest-homeassistant-custom-component` — Config-Flow (alle Pfade inkl.
  Reauth), Coordinator-Update, Entity-States, Command-Dispatch.
- **Ziel:** ≥95 % Coverage (Silver `test-coverage`).

---

## 9. Tooling & Release

- `uv` + `ruff` (line-length 79) + `ty`, `uv.lock` committed.
- Versionsgleichheit `manifest.json` ⇄ `pyproject.toml`.
- CI: HACS-Validierung, hassfest, ruff, pytest.
- Branches: `develop` → Docker-Test → Beta (`v0.x.yb<N>`, Pre-Release) → Stable.
- HACS: `manifest.json` (documentation, issue_tracker, codeowners), README mit Install-/
  Removal-Anleitung, GitHub-Releases, optional `brands/` Icon.

---

## 10. Offene Punkte / Annahmen

- Spike entscheidet finale Auth-Formvariante (A vs. B) und liefert exakte State-/Command-Schemata.
- Fehler-/Problem-`binary_sensor` bewusst **zurückgestellt** (YAGNI; später erweiterbar).
- `last_seen`-Sensor: nicht im Erstumfang.
- Repo wird vorerst **privat** angelegt; für die HACS-Listung später auf **public** stellen.
