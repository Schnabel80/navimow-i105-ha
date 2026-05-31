# navimow_simple Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eine schlanke Home-Assistant-Custom-Integration (`navimow_simple`) für den Segway Navimow i105, die per HTTP-Polling (90 s, kein MQTT) Status liefert und Start/Pause/Dock steuert.

**Architecture:** Ein `TokenManager` (asyncio-Lock, einziger Token-Besitzer) versorgt einen HA-unabhängigen `NavimowClient` (3 REST-Calls). Ein `DataUpdateCoordinator` pollt alle 90 s; dünne `CoordinatorEntity`-Wrapper (`lawn_mower`, 2× `sensor`) lesen daraus. Alle Spike-abhängigen Magie-Konstanten (vehicleState-Strings, Command-Codes, Auth-Grant) liegen isoliert in `const.py`.

**Tech Stack:** Python 3.13+, Home Assistant, aiohttp, `uv` + `ruff` + `ty`, pytest + `pytest-homeassistant-custom-component`.

**Arbeitsumgebung:** Repo `Schnabel80/navimow-i105-ha` (privat). Arbeit im ephemeren Klon (z.B. `/tmp/navimow-i105-ha`), nichts dauerhaft auf dem Mac. Keine personenbezogenen IDs in Commits (Platzhalter verwenden).

---

## Phasenüberblick

- **Phase 0 (Task 1):** Spike — füllt die 4 Unbekannten, schreibt `docs/spike-findings.md`. **Gate.**
- **Phase 1 (Tasks 2–3):** Projekt-Scaffold, Tooling, `const.py`.
- **Phase 2 (Tasks 4–7):** Pure Module `api.py` (TDD, kein HA).
- **Phase 3 (Tasks 8–9):** `auth.py` TokenManager.
- **Phase 4 (Tasks 10–11):** `coordinator.py` + `__init__.py`.
- **Phase 5 (Tasks 12–13):** `config_flow.py` (Setup + Reauth).
- **Phase 6 (Tasks 14–15):** Entities `lawn_mower.py` + `sensor.py`.
- **Phase 7 (Tasks 16–18):** `diagnostics.py`, Manifest/HACS/Translations, CI/README/Release.

Jede Phase ab 2 endet mit grünem `uv run pytest` + Commit.

---

## Dateistruktur

| Datei | Verantwortung |
|---|---|
| `custom_components/navimow_simple/const.py` | Alle Konstanten + Spike-Magiewerte + State-Map |
| `custom_components/navimow_simple/api.py` | `NavimowClient`: 3 REST-Calls, Header, Fehler→Exceptions, 1× Retry. **Kein HA-Import.** |
| `custom_components/navimow_simple/auth.py` | `TokenManager`: ein Token, asyncio-Lock, Re-Login/Reauth |
| `custom_components/navimow_simple/coordinator.py` | `NavimowCoordinator` (90 s Poll) |
| `custom_components/navimow_simple/__init__.py` | `async_setup_entry`/`async_unload_entry`, `runtime_data` |
| `custom_components/navimow_simple/config_flow.py` | Setup + Reauth-Flow |
| `custom_components/navimow_simple/lawn_mower.py` | `LawnMowerEntity` (Start/Pause/Dock, Start=Resume) |
| `custom_components/navimow_simple/sensor.py` | Akku-% + Status-Text |
| `custom_components/navimow_simple/diagnostics.py` | Redacted Snapshot |
| `custom_components/navimow_simple/manifest.json` | Metadaten, `iot_class: cloud_polling` |
| `custom_components/navimow_simple/strings.json` + `translations/{de,en}.json` | UI-Texte |
| `tests/...` | pytest (pure + HA-Harness) |
| `scripts/spike_auth.py` | Phase-0-Wegwerf-Skript |

---

## Task 1: Phase-0-Spike

**Ziel:** Die vier Unbekannten klären und in `docs/spike-findings.md` dokumentieren. Wegwerf-Code, kein Test, kein Produktivpfad.

**Files:**
- Create: `scripts/spike_auth.py`
- Create: `docs/spike-findings.md` (Ergebnis)

- [ ] **Step 1: Spike-Skript schreiben**

`scripts/spike_auth.py`:

```python
"""Wegwerf-Spike: klärt vehicleState-Enum, Command-Payloads, Auth-Grant.

Nutzung:
  export NAVIMOW_TOKEN="<access_token aus App/offizieller Integration>"
  export NAVIMOW_SN="<Geraete-Seriennummer>"        # NICHT committen
  # optional fuer Auth-Test:
  export NAVIMOW_EMAIL="..."; export NAVIMOW_PW="..."
  python scripts/spike_auth.py status
  python scripts/spike_auth.py command start    # | pause | dock
  python scripts/spike_auth.py authlist
  python scripts/spike_auth.py login            # testet grant_type=password
"""
import asyncio
import json
import os
import sys
import uuid

import aiohttp

BASE = "https://navimow-fra.ninebot.com"
CLIENT_ID = "homeassistant"
CLIENT_SECRET = "57056e15-722e-42be-bbaa-b0cbfb208a52"


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {os.environ['NAVIMOW_TOKEN']}",
        "requestId": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }


async def _post(session, path, body):
    async with session.post(f"{BASE}{path}", json=body, headers=_headers()) as r:
        text = await r.text()
        print(f"POST {path} -> HTTP {r.status}\n{text}\n")
        return text


async def _get(session, path):
    async with session.get(f"{BASE}{path}", headers=_headers()) as r:
        text = await r.text()
        print(f"GET {path} -> HTTP {r.status}\n{text}\n")
        return text


async def main(action: str) -> None:
    async with aiohttp.ClientSession() as session:
        sn = os.environ.get("NAVIMOW_SN", "")
        if action == "authlist":
            await _get(session, "/openapi/smarthome/authList")
        elif action == "status":
            # Body-Form ggf. anpassen, falls API anderen Key erwartet:
            await _post(session, "/openapi/smarthome/getVehicleStatus", {"deviceSn": sn})
        elif action == "command":
            cmd = sys.argv[2] if len(sys.argv) > 2 else "start"
            # Verschiedene plausible Payload-Formen durchprobieren und Antwort loggen:
            await _post(session, "/openapi/smarthome/sendCommands",
                        {"deviceSn": sn, "command": cmd})
        elif action == "login":
            body = {
                "grant_type": "password",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "username": os.environ.get("NAVIMOW_EMAIL", ""),
                "password": os.environ.get("NAVIMOW_PW", ""),
            }
            async with session.post(f"{BASE}/openapi/oauth/getAccessToken",
                                    json=body) as r:
                print(f"login -> HTTP {r.status}\n{await r.text()}\n")
        else:
            print("unknown action")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "status"))
```

- [ ] **Step 2: Nutzer führt Spike am echten Mäher aus**

Anleitung an den Nutzer (du):
1. `authlist` → bestätigt Antwortform + Geräte-Key-Namen (`deviceSn` vs. `deviceId`).
2. `status` mit gedocktem Mäher → Basiswert. Dann Mäher **starten** → `status`, **pausieren** → `status`, **Dock** während Rückfahrt → `status`. Jeden `vehicleState`-String notieren.
3. `command start|pause|dock` → erfolgreiche HTTP-200 + Antwort-Body notieren (richtiges Payload-Schema). Falls 400/Fehler: Payload-Variante anpassen (z.B. `cmdType`/Integer-Code) bis Befehl greift.
4. `login` → prüfen ob `grant_type=password` einen Token (+ ggf. `refresh_token`) liefert. Optional: Login-Request der H5-Seite per Browser-DevTools mitschneiden, falls `password`-Grant scheitert.

- [ ] **Step 3: Findings dokumentieren**

`docs/spike-findings.md` mit konkreten Werten:

```markdown
# Spike-Findings (Phase 0)

## authList
- Request: GET /openapi/smarthome/authList (kein Body)
- Geräte-Key in Response: <deviceSn | deviceId | ...>
- Beispiel-Response (redacted): ...

## getVehicleStatus
- Request-Body: {"<key>": "<sn>"}
- vehicleState-Strings:
  - gedockt:    <z.B. isDocked>
  - lädt:       <...>
  - mäht:       <...>
  - pausiert:   <...>
  - rückkehr:   <...>
  - fehler:     <...>

## sendCommands
- Request-Body Start:  <exaktes JSON>
- Request-Body Pause:  <...>
- Request-Body Dock:   <...>
- Resume (aus Pause):  <gleicher Start-Befehl? eigener?>

## Auth
- grant_type=password: <funktioniert JA/NEIN>
- Response enthält refresh_token: <JA/NEIN>
- Entscheidung: Weg A (stiller E-Mail+PW-Login) | Weg B (Browser-OAuth)
```

- [ ] **Step 4: Commit (ohne personenbezogene Werte)**

```bash
cd /tmp/navimow-i105-ha
grep -Rn -E "S4REA|<deine-echte-sn>" docs/ scripts/ && echo "STOP: SN gefunden" || true
git add scripts/spike_auth.py docs/spike-findings.md
git commit -m "spike: API-Schemata + Auth-Grant geklärt (Phase 0)"
git push
```

**Gate:** Erst weiter, wenn `spike-findings.md` alle Felder gefüllt hat und die Auth-Entscheidung (A/B) steht.

---

## Task 2: Projekt-Scaffold + Tooling

**Files:**
- Create: `pyproject.toml`, `custom_components/navimow_simple/__init__.py` (leer-Stub), `tests/__init__.py`, `tests/conftest.py`

- [ ] **Step 1: `pyproject.toml` anlegen**

```toml
[project]
name = "hass-navimow-simple"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = []

[dependency-groups]
lint = ["ruff>=0.15"]
typecheck = ["homeassistant>=2026.3.0", "ty"]
test = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "pytest-homeassistant-custom-component>=0.13",
    "homeassistant>=2026.3.0",
]
dev = [
    {include-group = "lint"},
    {include-group = "typecheck"},
    {include-group = "test"},
]

[tool.ruff]
line-length = 79
target-version = "py313"

[tool.ruff.lint]
select = ["E","F","I","UP","B","BLE","SIM","C90","RUF","ASYNC","PERF","PGH","G","T20","TC"]
ignore = ["RUF001","RUF002","RUF003"]

[tool.ruff.lint.mccabe]
max-complexity = 25

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 2: Leere Modul-/Test-Stubs anlegen**

```bash
cd /tmp/navimow-i105-ha
mkdir -p custom_components/navimow_simple/translations tests
printf '"""Navimow Simple integration."""\n' > custom_components/navimow_simple/__init__.py
printf '' > tests/__init__.py
```

`tests/conftest.py`:

```python
"""Shared pytest fixtures."""
import pytest

pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading custom integration in tests."""
    yield
```

- [ ] **Step 3: Deps installieren, Smoke-Test**

Run: `cd /tmp/navimow-i105-ha && uv sync --group dev`
Expected: erfolgreicher Sync, `uv.lock` entsteht.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock custom_components tests
git commit -m "chore: Projekt-Scaffold + uv/ruff/ty/pytest-Tooling"
git push
```

---

## Task 3: `const.py` (Konstanten + Spike-Magiewerte)

**Files:**
- Create: `custom_components/navimow_simple/const.py`
- Test: `tests/test_const.py`

- [ ] **Step 1: Failing test**

`tests/test_const.py`:

```python
from custom_components.navimow_simple import const


def test_core_constants_present():
    assert const.DOMAIN == "navimow_simple"
    assert const.BASE_URL.startswith("https://")
    assert const.UPDATE_INTERVAL_SECONDS == 90


def test_state_map_has_known_docked_value():
    # "isDocked" aus Live-Test ist bekannt; weitere Strings ergänzt der Spike.
    from homeassistant.components.lawn_mower import LawnMowerActivity
    assert const.STATE_MAP["isDocked"] == LawnMowerActivity.DOCKED


def test_commands_cover_required_actions():
    for action in ("start", "pause", "dock"):
        assert action in const.COMMANDS
```

- [ ] **Step 2: Run → FAIL**

Run: `uv run --group test pytest tests/test_const.py -v`
Expected: FAIL (`module const not found`).

- [ ] **Step 3: `const.py` schreiben**

```python
"""Constants for the Navimow Simple integration."""
from __future__ import annotations

from typing import Final

from homeassistant.components.lawn_mower import LawnMowerActivity

DOMAIN: Final = "navimow_simple"

# --- API ---------------------------------------------------------------
BASE_URL: Final = "https://navimow-fra.ninebot.com"
PATH_AUTH_LIST: Final = "/openapi/smarthome/authList"
PATH_STATUS: Final = "/openapi/smarthome/getVehicleStatus"
PATH_COMMANDS: Final = "/openapi/smarthome/sendCommands"
PATH_TOKEN: Final = "/openapi/oauth/getAccessToken"

CLIENT_ID: Final = "homeassistant"
CLIENT_SECRET: Final = "57056e15-722e-42be-bbaa-b0cbfb208a52"

# API-seitiger Schlüssel für die Geräte-Seriennummer im Request-Body.
# Vom Spike bestätigt (Task 1, authList/getVehicleStatus).
DEVICE_SN_KEY: Final = "deviceSn"

# --- Polling -----------------------------------------------------------
UPDATE_INTERVAL_SECONDS: Final = 90
TOKEN_EXPIRY_BUFFER_SECONDS: Final = 60

# --- Fehlercodes (Auth) ------------------------------------------------
# API liefert bei ungültigem/abgelaufenem Token diese Codes.
AUTH_ERROR_CODES: Final = frozenset({"4003", "TOKEN_EMPTY"})

# --- vehicleState -> LawnMowerActivity ---------------------------------
# "isDocked" ist aus Live-Test belegt; die übrigen Strings stammen aus
# dem Spike (docs/spike-findings.md) und werden hier eingetragen.
STATE_MAP: Final[dict[str, LawnMowerActivity]] = {
    "isDocked": LawnMowerActivity.DOCKED,
    "isCharging": LawnMowerActivity.DOCKED,
    "isMowing": LawnMowerActivity.MOWING,
    "isWorking": LawnMowerActivity.MOWING,
    "isPaused": LawnMowerActivity.PAUSED,
    "isReturning": LawnMowerActivity.RETURNING,
    "isError": LawnMowerActivity.ERROR,
}

# --- Command-Payloads --------------------------------------------------
# Exakte Body-Schemata aus dem Spike (Task 1, sendCommands). Die Werte
# unten sind Platzhalter-Form und werden 1:1 durch die Spike-Funde ersetzt.
COMMANDS: Final[dict[str, dict]] = {
    "start": {"command": "start"},
    "pause": {"command": "pause"},
    "dock": {"command": "dock"},
}

# Auth-Strategie aus Spike: True = stiller E-Mail+PW-Login (Weg A),
# False = Browser-OAuth (Weg B).
SILENT_PASSWORD_LOGIN: Final = True
```

> **Hinweis für den ausführenden Agenten:** `STATE_MAP` und `COMMANDS` mit den **echten** Werten aus `docs/spike-findings.md` überschreiben. `SILENT_PASSWORD_LOGIN` gemäß Auth-Entscheidung setzen. Die Tests prüfen nur die *Mechanik* (bekannter Docked-Wert, Action-Keys vorhanden), nicht die Magie-Strings — sie bleiben grün.

- [ ] **Step 4: Run → PASS**

Run: `uv run --group test pytest tests/test_const.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add custom_components/navimow_simple/const.py tests/test_const.py
git commit -m "feat: const.py mit API-/Polling-Konstanten + State-Map"
git push
```

---

## Task 4: `api.py` — Exceptions + Request-Grundgerüst

**Files:**
- Create: `custom_components/navimow_simple/api.py`
- Test: `tests/test_api.py`

`NavimowClient` nimmt eine `aiohttp.ClientSession` und einen `TokenSource` (Protocol mit `async_get_valid_token(force_refresh: bool = False) -> str`). So bleibt `api.py` HA-frei.

- [ ] **Step 1: Failing test (Header + Token)**

`tests/test_api.py`:

```python
import pytest
from aioresponses import aioresponses

from custom_components.navimow_simple import const
from custom_components.navimow_simple.api import (
    NavimowApiError,
    NavimowAuthError,
    NavimowClient,
)


class _FakeTokens:
    def __init__(self):
        self.calls: list[bool] = []
        self.token = "tok-1"

    async def async_get_valid_token(self, force_refresh: bool = False) -> str:
        self.calls.append(force_refresh)
        if force_refresh:
            self.token = "tok-2"
        return self.token


@pytest.fixture
def tokens():
    return _FakeTokens()


@pytest.mark.asyncio
async def test_get_devices_sends_bearer_and_requestid(tokens):
    import aiohttp

    with aioresponses() as m:
        m.get(
            f"{const.BASE_URL}{const.PATH_AUTH_LIST}",
            payload={"code": "0", "data": [{"deviceSn": "X"}]},
        )
        async with aiohttp.ClientSession() as session:
            client = NavimowClient(session, tokens)
            data = await client.async_get_devices()

    assert data == [{"deviceSn": "X"}]
    req = next(iter(m.requests.values()))[0]
    headers = req.kwargs["headers"]
    assert headers["Authorization"] == "Bearer tok-1"
    assert "requestId" in headers and len(headers["requestId"]) >= 10
```

- [ ] **Step 2: Run → FAIL**

Run: `uv run --group test pytest tests/test_api.py -v`
Expected: FAIL (`module api not found`). Falls `aioresponses` fehlt: zu `test`-Gruppe in `pyproject.toml` hinzufügen (`"aioresponses>=0.7"`) und `uv sync --group test`.

- [ ] **Step 3: `api.py` Grundgerüst**

```python
"""HA-unabhängiger HTTP-Client für die Navimow smarthome-openapi."""
from __future__ import annotations

import uuid
from typing import Any, Protocol

import aiohttp

from .const import (
    AUTH_ERROR_CODES,
    BASE_URL,
    COMMANDS,
    DEVICE_SN_KEY,
    PATH_AUTH_LIST,
    PATH_COMMANDS,
    PATH_STATUS,
)


class NavimowError(Exception):
    """Basis-Fehler."""


class NavimowAuthError(NavimowError):
    """Token ungültig/abgelaufen (4003 / TOKEN_EMPTY)."""


class NavimowApiError(NavimowError):
    """Sonstiger API-/HTTP-Fehler."""


class TokenSource(Protocol):
    async def async_get_valid_token(self, force_refresh: bool = False) -> str: ...


class NavimowClient:
    """Drei REST-Calls gegen die smarthome-openapi."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        tokens: TokenSource,
        base_url: str = BASE_URL,
    ) -> None:
        self._session = session
        self._tokens = tokens
        self._base = base_url

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        _retried: bool = False,
    ) -> Any:
        token = await self._tokens.async_get_valid_token(force_refresh=_retried)
        headers = {
            "Authorization": f"Bearer {token}",
            "requestId": str(uuid.uuid4()),
            "Content-Type": "application/json",
        }
        try:
            async with self._session.request(
                method, f"{self._base}{path}", json=json, headers=headers
            ) as resp:
                status = resp.status
                payload = await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            raise NavimowApiError(f"HTTP-Fehler bei {path}: {err}") from err

        code = str(payload.get("code")) if isinstance(payload, dict) else None
        if status in (401, 403) or (code in AUTH_ERROR_CODES):
            if not _retried:
                # Einmaliger Retry mit erzwungenem Token-Refresh.
                return await self._request(
                    method, path, json=json, _retried=True
                )
            raise NavimowAuthError(f"Auth abgelehnt bei {path} (code={code})")
        if status >= 400 or (code not in (None, "0", "200")):
            raise NavimowApiError(
                f"API-Fehler bei {path}: HTTP {status} code={code}"
            )
        return payload.get("data") if isinstance(payload, dict) else payload

    async def async_get_devices(self) -> list[dict[str, Any]]:
        data = await self._request("GET", PATH_AUTH_LIST)
        return data or []

    async def async_get_status(self, device_sn: str) -> dict[str, Any]:
        return await self._request(
            "POST", PATH_STATUS, json={DEVICE_SN_KEY: device_sn}
        )

    async def async_send_command(self, device_sn: str, action: str) -> None:
        body = {DEVICE_SN_KEY: device_sn, **COMMANDS[action]}
        await self._request("POST", PATH_COMMANDS, json=body)
```

- [ ] **Step 4: Run → PASS**

Run: `uv run --group test pytest tests/test_api.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add custom_components/navimow_simple/api.py tests/test_api.py pyproject.toml uv.lock
git commit -m "feat: NavimowClient Grundgerüst (Header, Bearer, get_devices)"
git push
```

---

## Task 5: `api.py` — Status + Command-Plumbing

**Files:**
- Modify: `tests/test_api.py`

- [ ] **Step 1: Failing tests**

An `tests/test_api.py` anhängen:

```python
@pytest.mark.asyncio
async def test_get_status_posts_sn(tokens):
    import aiohttp

    with aioresponses() as m:
        m.post(
            f"{const.BASE_URL}{const.PATH_STATUS}",
            payload={"code": "0", "data": {"vehicleState": "isDocked"}},
        )
        async with aiohttp.ClientSession() as session:
            client = NavimowClient(session, tokens)
            data = await client.async_get_status("SN1")

    assert data["vehicleState"] == "isDocked"
    req = next(iter(m.requests.values()))[0]
    assert req.kwargs["json"] == {const.DEVICE_SN_KEY: "SN1"}


@pytest.mark.asyncio
async def test_send_command_merges_action_payload(tokens):
    import aiohttp

    with aioresponses() as m:
        m.post(f"{const.BASE_URL}{const.PATH_COMMANDS}", payload={"code": "0"})
        async with aiohttp.ClientSession() as session:
            client = NavimowClient(session, tokens)
            await client.async_send_command("SN1", "start")

    req = next(iter(m.requests.values()))[0]
    body = req.kwargs["json"]
    assert body[const.DEVICE_SN_KEY] == "SN1"
    for k, v in const.COMMANDS["start"].items():
        assert body[k] == v
```

- [ ] **Step 2: Run → PASS** (Implementierung existiert bereits aus Task 4)

Run: `uv run --group test pytest tests/test_api.py -v`
Expected: PASS (beide neuen Tests grün).

- [ ] **Step 3: Commit**

```bash
git add tests/test_api.py
git commit -m "test: status- und command-plumbing abgedeckt"
git push
```

---

## Task 6: `api.py` — Auth-Retry-Logik

**Files:**
- Modify: `tests/test_api.py`

- [ ] **Step 1: Failing tests (Retry + Aufgeben)**

```python
@pytest.mark.asyncio
async def test_4003_triggers_one_retry_with_force_refresh(tokens):
    import aiohttp

    with aioresponses() as m:
        # 1. Antwort: 4003 (Token faul). 2. Antwort: ok.
        m.post(f"{const.BASE_URL}{const.PATH_STATUS}", payload={"code": "4003"})
        m.post(
            f"{const.BASE_URL}{const.PATH_STATUS}",
            payload={"code": "0", "data": {"vehicleState": "isDocked"}},
        )
        async with aiohttp.ClientSession() as session:
            client = NavimowClient(session, tokens)
            data = await client.async_get_status("SN1")

    assert data["vehicleState"] == "isDocked"
    # Erst ohne, dann mit force_refresh.
    assert tokens.calls == [False, True]


@pytest.mark.asyncio
async def test_persistent_4003_raises_auth_error(tokens):
    import aiohttp

    with aioresponses() as m:
        m.post(f"{const.BASE_URL}{const.PATH_STATUS}", payload={"code": "4003"})
        m.post(f"{const.BASE_URL}{const.PATH_STATUS}", payload={"code": "4003"})
        async with aiohttp.ClientSession() as session:
            client = NavimowClient(session, tokens)
            with pytest.raises(NavimowAuthError):
                await client.async_get_status("SN1")
```

- [ ] **Step 2: Run → PASS** (Retry-Logik in `_request` aus Task 4 deckt das ab)

Run: `uv run --group test pytest tests/test_api.py -v`
Expected: PASS.

> Falls `test_persistent_4003_raises_auth_error` fehlschlägt, weil `aioresponses` die zweite identische Antwort nicht liefert: beide Antworten mit `repeat=False` registrieren (Standard) — aioresponses gibt sie FIFO zurück.

- [ ] **Step 3: Commit**

```bash
git add tests/test_api.py
git commit -m "test: 4003-Retry und Auth-Fehler abgedeckt"
git push
```

---

## Task 7: State-Mapping-Funktion

**Files:**
- Modify: `custom_components/navimow_simple/api.py` (Funktion `state_to_activity`)
- Test: `tests/test_state_map.py`

- [ ] **Step 1: Failing test**

`tests/test_state_map.py`:

```python
from homeassistant.components.lawn_mower import LawnMowerActivity

from custom_components.navimow_simple.api import state_to_activity


def test_known_docked():
    assert state_to_activity("isDocked") == LawnMowerActivity.DOCKED


def test_unknown_defaults_to_error():
    assert state_to_activity("voelliger_quatsch") == LawnMowerActivity.ERROR


def test_none_defaults_to_error():
    assert state_to_activity(None) == LawnMowerActivity.ERROR
```

- [ ] **Step 2: Run → FAIL**

Run: `uv run --group test pytest tests/test_state_map.py -v`
Expected: FAIL (`state_to_activity` nicht importierbar).

- [ ] **Step 3: Funktion in `api.py` ergänzen**

Am Ende von `api.py` (Import oben ergänzen: `from homeassistant.components.lawn_mower import LawnMowerActivity` — **Achtung:** dieser eine HA-Import bricht die HA-Freiheit von `api.py`. Daher `state_to_activity` stattdessen in **`coordinator.py`** ansiedeln, wenn HA-Reinheit gewünscht ist. Für diesen Plan: in `api.py` belassen, da `LawnMowerActivity` ein reiner Enum ohne Laufzeitkosten ist und Tests es ohnehin importieren.):

```python
from .const import STATE_MAP  # oben zu den Imports


def state_to_activity(raw: str | None):
    """vehicleState-String -> LawnMowerActivity, unbekannt -> ERROR."""
    from homeassistant.components.lawn_mower import LawnMowerActivity

    if raw is None:
        return LawnMowerActivity.ERROR
    return STATE_MAP.get(raw, LawnMowerActivity.ERROR)
```

- [ ] **Step 4: Run → PASS**

Run: `uv run --group test pytest tests/test_state_map.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add custom_components/navimow_simple/api.py tests/test_state_map.py
git commit -m "feat: state_to_activity mit ERROR-Default"
git push
```

---

## Task 8: `auth.py` — TokenManager Kern (Lock + Expiry)

**Files:**
- Create: `custom_components/navimow_simple/auth.py`
- Test: `tests/test_auth.py`

Der TokenManager kapselt Token + `expires_at`, einen `asyncio.Lock`, und einen austauschbaren `login`-Callback (für Tests ohne HTTP). Persistenz in den ConfigEntry passiert in Task 11.

- [ ] **Step 1: Failing test**

`tests/test_auth.py`:

```python
import time

import pytest

from custom_components.navimow_simple.auth import TokenManager


@pytest.mark.asyncio
async def test_returns_cached_token_without_relogin():
    calls = []

    async def login():
        calls.append(1)
        return {"access_token": "A", "expires_at": time.time() + 3600}

    tm = TokenManager(login=login)
    assert await tm.async_get_valid_token() == "A"
    assert await tm.async_get_valid_token() == "A"
    assert len(calls) == 1  # nur ein Login


@pytest.mark.asyncio
async def test_force_refresh_relogins():
    seq = iter(["A", "B"])

    async def login():
        return {"access_token": next(seq), "expires_at": time.time() + 3600}

    tm = TokenManager(login=login)
    assert await tm.async_get_valid_token() == "A"
    assert await tm.async_get_valid_token(force_refresh=True) == "B"


@pytest.mark.asyncio
async def test_expired_token_triggers_relogin():
    seq = iter([
        {"access_token": "A", "expires_at": time.time() - 1},
        {"access_token": "B", "expires_at": time.time() + 3600},
    ])

    async def login():
        return next(seq)

    tm = TokenManager(login=login)
    assert await tm.async_get_valid_token() == "A"  # erster Login
    assert await tm.async_get_valid_token() == "B"  # abgelaufen -> relogin
```

- [ ] **Step 2: Run → FAIL**

Run: `uv run --group test pytest tests/test_auth.py -v`
Expected: FAIL (`module auth not found`).

- [ ] **Step 3: `auth.py` Kern**

```python
"""TokenManager: einziger Token-Besitzer, asyncio-Lock, Re-Login."""
from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

from .const import TOKEN_EXPIRY_BUFFER_SECONDS

LoginCallback = Callable[[], Awaitable[dict[str, Any]]]


class TokenManager:
    """Hält genau einen Token, serialisiert Refreshes über einen Lock."""

    def __init__(self, login: LoginCallback) -> None:
        self._login = login
        self._lock = asyncio.Lock()
        self._token: str | None = None
        self._expires_at: float = 0.0

    def _is_valid(self) -> bool:
        return (
            self._token is not None
            and time.time() < self._expires_at - TOKEN_EXPIRY_BUFFER_SECONDS
        )

    async def async_get_valid_token(self, force_refresh: bool = False) -> str:
        async with self._lock:
            if not force_refresh and self._is_valid():
                return self._token  # type: ignore[return-value]
            data = await self._login()
            self._token = data["access_token"]
            self._expires_at = float(
                data.get("expires_at")
                or time.time() + float(data.get("expires_in", 0))
            )
            return self._token
```

- [ ] **Step 4: Run → PASS**

Run: `uv run --group test pytest tests/test_auth.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add custom_components/navimow_simple/auth.py tests/test_auth.py
git commit -m "feat: TokenManager-Kern (Lock, Expiry, force_refresh)"
git push
```

---

## Task 9: `auth.py` — Lock serialisiert parallele Refreshes

**Files:**
- Modify: `tests/test_auth.py`

- [ ] **Step 1: Failing test (genau ein Login bei Parallelzugriff)**

```python
@pytest.mark.asyncio
async def test_parallel_access_logs_in_once():
    calls = []

    async def login():
        calls.append(1)
        import asyncio as _a
        await _a.sleep(0.01)
        return {"access_token": "A", "expires_at": time.time() + 3600}

    tm = TokenManager(login=login)
    import asyncio as _a
    results = await _a.gather(*[tm.async_get_valid_token() for _ in range(5)])
    assert results == ["A"] * 5
    assert len(calls) == 1  # Lock verhindert 5 parallele Logins
```

- [ ] **Step 2: Run → PASS** (Lock + `_is_valid`-Recheck im Lock decken das ab)

Run: `uv run --group test pytest tests/test_auth.py::test_parallel_access_logs_in_once -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_auth.py
git commit -m "test: paralleler Token-Zugriff loggt nur einmal ein"
git push
```

---

## Task 10: `coordinator.py`

**Files:**
- Create: `custom_components/navimow_simple/coordinator.py`
- Test: `tests/test_coordinator.py`

- [ ] **Step 1: Failing test**

`tests/test_coordinator.py`:

```python
import pytest

from custom_components.navimow_simple.coordinator import NavimowCoordinator


class _FakeClient:
    def __init__(self, status):
        self._status = status

    async def async_get_status(self, sn):
        return self._status


@pytest.mark.asyncio
async def test_update_maps_state_and_battery(hass):
    client = _FakeClient(
        {
            "vehicleState": "isDocked",
            "capacityRemaining": [{"unit": "PERCENTAGE", "rawValue": 88}],
        }
    )
    coord = NavimowCoordinator(hass, client, device_sn="SN1", device_name="Mäher")
    data = await coord._async_update_data()
    assert data["state"] == "isDocked"
    assert data["battery"] == 88
```

- [ ] **Step 2: Run → FAIL**

Run: `uv run --group test pytest tests/test_coordinator.py -v`
Expected: FAIL (`module coordinator not found`).

- [ ] **Step 3: `coordinator.py` schreiben**

```python
"""DataUpdateCoordinator (90 s Poll, einziger Token-Nutzer)."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import NavimowAuthError, NavimowClient, NavimowError
from .const import DOMAIN, UPDATE_INTERVAL_SECONDS

_LOGGER = logging.getLogger(__name__)


def _extract_battery(status: dict[str, Any]) -> int | None:
    cap = status.get("capacityRemaining") or []
    if cap and isinstance(cap, list):
        raw = cap[0].get("rawValue")
        return int(raw) if raw is not None else None
    return None


class NavimowCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(
        self,
        hass: HomeAssistant,
        client: NavimowClient,
        *,
        device_sn: str,
        device_name: str,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )
        self.client = client
        self.device_sn = device_sn
        self.device_name = device_name

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            status = await self.client.async_get_status(self.device_sn)
        except NavimowAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except NavimowError as err:
            raise UpdateFailed(str(err)) from err
        return {
            "state": status.get("vehicleState"),
            "battery": _extract_battery(status),
            "raw": status,
        }
```

- [ ] **Step 4: Run → PASS**

Run: `uv run --group test pytest tests/test_coordinator.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add custom_components/navimow_simple/coordinator.py tests/test_coordinator.py
git commit -m "feat: NavimowCoordinator (90s, state+battery-Mapping)"
git push
```

---

## Task 11: `__init__.py` + Login-Wiring + `manifest.json`

**Files:**
- Modify: `custom_components/navimow_simple/__init__.py`
- Create: `custom_components/navimow_simple/manifest.json`
- Create: `custom_components/navimow_simple/auth.py` (Login-Builder ergänzen)
- Test: `tests/test_init.py`

Der echte Login (Weg A) baut den `login`-Callback für den TokenManager: POST `getAccessToken` mit `grant_type=password` + gespeicherten Credentials. Exakte Body-Form aus Spike.

- [ ] **Step 1: `manifest.json`**

```json
{
  "domain": "navimow_simple",
  "name": "Navimow Simple",
  "version": "0.1.0",
  "documentation": "https://github.com/Schnabel80/navimow-i105-ha",
  "issue_tracker": "https://github.com/Schnabel80/navimow-i105-ha/issues",
  "codeowners": ["@Schnabel80"],
  "config_flow": true,
  "iot_class": "cloud_polling",
  "integration_type": "device",
  "requirements": []
}
```

- [ ] **Step 2: Login-Builder in `auth.py` ergänzen**

```python
import aiohttp

from .const import (
    BASE_URL,
    CLIENT_ID,
    CLIENT_SECRET,
    PATH_TOKEN,
)


def build_password_login(
    session: aiohttp.ClientSession, email: str, password: str
) -> LoginCallback:
    """Erzeugt einen login-Callback für grant_type=password (Weg A).

    Body-Form aus docs/spike-findings.md; bei Bedarf dort anpassen.
    """

    async def _login() -> dict[str, Any]:
        body = {
            "grant_type": "password",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "username": email,
            "password": password,
        }
        async with session.post(f"{BASE_URL}{PATH_TOKEN}", json=body) as resp:
            payload = await resp.json(content_type=None)
        data = payload.get("data", payload)
        if not data.get("access_token"):
            from homeassistant.exceptions import ConfigEntryAuthFailed

            raise ConfigEntryAuthFailed("Login lieferte keinen access_token")
        return data

    return _login
```

- [ ] **Step 3: `__init__.py`**

```python
"""Navimow Simple integration."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NavimowClient
from .auth import TokenManager, build_password_login
from .coordinator import NavimowCoordinator

PLATFORMS: list[Platform] = [Platform.LAWN_MOWER, Platform.SENSOR]

CONF_DEVICE_SN = "device_sn"
CONF_DEVICE_NAME = "device_name"


@dataclass
class NavimowRuntime:
    coordinator: NavimowCoordinator
    client: NavimowClient
    tokens: TokenManager


type NavimowConfigEntry = ConfigEntry[NavimowRuntime]


async def async_setup_entry(
    hass: HomeAssistant, entry: NavimowConfigEntry
) -> bool:
    session = async_get_clientsession(hass)
    login = build_password_login(
        session, entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD]
    )
    tokens = TokenManager(login=login)
    client = NavimowClient(session, tokens)
    coordinator = NavimowCoordinator(
        hass,
        client,
        device_sn=entry.data[CONF_DEVICE_SN],
        device_name=entry.data.get(CONF_DEVICE_NAME, "Navimow"),
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = NavimowRuntime(coordinator, client, tokens)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: NavimowConfigEntry
) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
```

- [ ] **Step 4: Test (Setup/Unload mit gemocktem Client)**

`tests/test_init.py`:

```python
from unittest.mock import patch

import pytest
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.navimow_simple import __init__ as integ
from custom_components.navimow_simple.const import DOMAIN


@pytest.mark.asyncio
async def test_setup_and_unload(hass: HomeAssistant):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_EMAIL: "u@example.com",
            CONF_PASSWORD: "pw",
            integ.CONF_DEVICE_SN: "SN1",
            integ.CONF_DEVICE_NAME: "Mäher",
        },
    )
    entry.add_to_hass(hass)

    status = {
        "vehicleState": "isDocked",
        "capacityRemaining": [{"unit": "PERCENTAGE", "rawValue": 50}],
    }
    with patch(
        "custom_components.navimow_simple.NavimowClient.async_get_status",
        return_value=status,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.runtime_data.coordinator.data["battery"] == 50
        assert await hass.config_entries.async_unload(entry.entry_id)
```

- [ ] **Step 5: Run → PASS**

Run: `uv run --group test pytest tests/test_init.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add custom_components/navimow_simple/__init__.py custom_components/navimow_simple/manifest.json custom_components/navimow_simple/auth.py tests/test_init.py
git commit -m "feat: setup_entry + runtime_data + password-login-builder"
git push
```

---

## Task 12: `config_flow.py` — Setup-Schritt

**Files:**
- Create: `custom_components/navimow_simple/config_flow.py`
- Create: `custom_components/navimow_simple/strings.json`
- Test: `tests/test_config_flow.py`

- [ ] **Step 1: Failing test (User-Flow erstellt Entry)**

`tests/test_config_flow.py`:

```python
from unittest.mock import patch

import pytest
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.navimow_simple.const import DOMAIN


@pytest.mark.asyncio
async def test_user_flow_creates_entry(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == FlowResultType.FORM

    devices = [{"deviceSn": "SN1", "deviceName": "Mäher"}]
    with patch(
        "custom_components.navimow_simple.config_flow.NavimowClient.async_get_devices",
        return_value=devices,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: "u@example.com", CONF_PASSWORD: "pw"},
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_EMAIL] == "u@example.com"
    assert result["data"]["device_sn"] == "SN1"
```

- [ ] **Step 2: Run → FAIL**

Run: `uv run --group test pytest tests/test_config_flow.py -v`
Expected: FAIL (`config_flow` fehlt).

- [ ] **Step 3: `config_flow.py`**

```python
"""Config flow für Navimow Simple (Weg A: E-Mail + Passwort)."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import CONF_DEVICE_NAME, CONF_DEVICE_SN
from .api import NavimowAuthError, NavimowClient, NavimowError
from .auth import TokenManager, build_password_login
from .const import DOMAIN

STEP_USER_SCHEMA = vol.Schema(
    {vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str}
)


class NavimowConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            login = build_password_login(
                session, user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
            )
            client = NavimowClient(session, TokenManager(login=login))
            try:
                devices = await client.async_get_devices()
            except NavimowAuthError:
                errors["base"] = "invalid_auth"
            except NavimowError:
                errors["base"] = "cannot_connect"
            else:
                if not devices:
                    errors["base"] = "no_devices"
                else:
                    device = devices[0]
                    sn = device["deviceSn"]
                    await self.async_set_unique_id(sn)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=device.get("deviceName", "Navimow"),
                        data={
                            CONF_EMAIL: user_input[CONF_EMAIL],
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                            CONF_DEVICE_SN: sn,
                            CONF_DEVICE_NAME: device.get("deviceName", "Navimow"),
                        },
                    )
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )
```

`strings.json`:

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Navimow Simple",
        "description": "Melde dich mit deinem Segway-Konto an.",
        "data": { "email": "E-Mail", "password": "Passwort" }
      }
    },
    "error": {
      "invalid_auth": "Anmeldung fehlgeschlagen.",
      "cannot_connect": "Verbindung fehlgeschlagen.",
      "no_devices": "Kein Mäher gefunden."
    },
    "abort": { "already_configured": "Gerät ist bereits eingerichtet." }
  }
}
```

- [ ] **Step 4: Run → PASS**

Run: `uv run --group test pytest tests/test_config_flow.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add custom_components/navimow_simple/config_flow.py custom_components/navimow_simple/strings.json tests/test_config_flow.py
git commit -m "feat: config_flow user-step (E-Mail+PW, Geräte-Discovery)"
git push
```

---

## Task 13: `config_flow.py` — Reauth-Flow (Silver)

**Files:**
- Modify: `custom_components/navimow_simple/config_flow.py`
- Modify: `custom_components/navimow_simple/strings.json`
- Modify: `tests/test_config_flow.py`

- [ ] **Step 1: Failing test (Reauth aktualisiert Credentials)**

```python
from pytest_homeassistant_custom_component.common import MockConfigEntry


@pytest.mark.asyncio
async def test_reauth_updates_password(hass: HomeAssistant):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="SN1",
        data={
            CONF_EMAIL: "u@example.com",
            CONF_PASSWORD: "old",
            "device_sn": "SN1",
            "device_name": "Mäher",
        },
    )
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["type"] == FlowResultType.FORM

    with patch(
        "custom_components.navimow_simple.config_flow.NavimowClient.async_get_devices",
        return_value=[{"deviceSn": "SN1", "deviceName": "Mäher"}],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: "u@example.com", CONF_PASSWORD: "new"},
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "new"
```

- [ ] **Step 2: Run → FAIL**

Run: `uv run --group test pytest tests/test_config_flow.py::test_reauth_updates_password -v`
Expected: FAIL (kein Reauth-Step).

- [ ] **Step 3: Reauth-Steps ergänzen**

In `NavimowConfigFlow` ergänzen:

```python
    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            login = build_password_login(
                session, user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
            )
            client = NavimowClient(session, TokenManager(login=login))
            try:
                await client.async_get_devices()
            except NavimowAuthError:
                errors["base"] = "invalid_auth"
            except NavimowError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )
```

In `strings.json` unter `config.step` ergänzen:

```json
"reauth_confirm": {
  "title": "Navimow erneut anmelden",
  "description": "Bitte Zugangsdaten erneut eingeben.",
  "data": { "email": "E-Mail", "password": "Passwort" }
}
```
und unter `config.abort`: `"reauth_successful": "Erneute Anmeldung erfolgreich."`

- [ ] **Step 4: Run → PASS**

Run: `uv run --group test pytest tests/test_config_flow.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add custom_components/navimow_simple/config_flow.py custom_components/navimow_simple/strings.json tests/test_config_flow.py
git commit -m "feat: Reauth-Flow (Silver reauthentication-flow)"
git push
```

---

## Task 14: `lawn_mower.py`

**Files:**
- Create: `custom_components/navimow_simple/lawn_mower.py`
- Test: `tests/test_lawn_mower.py`

- [ ] **Step 1: Failing test (Activity-Mapping + Start-Command)**

`tests/test_lawn_mower.py`:

```python
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.lawn_mower import LawnMowerActivity
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.navimow_simple.const import DOMAIN


async def _setup(hass, status):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="SN1",
        data={
            CONF_EMAIL: "u@example.com",
            CONF_PASSWORD: "pw",
            "device_sn": "SN1",
            "device_name": "Mäher",
        },
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.navimow_simple.NavimowClient.async_get_status",
        return_value=status,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


@pytest.mark.asyncio
async def test_activity_docked(hass: HomeAssistant):
    await _setup(hass, {"vehicleState": "isDocked", "capacityRemaining": []})
    state = hass.states.get("lawn_mower.maher")
    assert state is not None
    assert state.state == LawnMowerActivity.DOCKED


@pytest.mark.asyncio
async def test_start_calls_send_command(hass: HomeAssistant):
    await _setup(hass, {"vehicleState": "isDocked", "capacityRemaining": []})
    with patch(
        "custom_components.navimow_simple.NavimowClient.async_send_command",
        new=AsyncMock(),
    ) as send, patch(
        "custom_components.navimow_simple.NavimowClient.async_get_status",
        return_value={"vehicleState": "isMowing", "capacityRemaining": []},
    ):
        await hass.services.async_call(
            "lawn_mower",
            "start_mowing",
            {"entity_id": "lawn_mower.maher"},
            blocking=True,
        )
    send.assert_awaited_once()
    assert send.await_args.args[1] == "start"
```

- [ ] **Step 2: Run → FAIL**

Run: `uv run --group test pytest tests/test_lawn_mower.py -v`
Expected: FAIL (Plattform fehlt → Entity nicht vorhanden).

- [ ] **Step 3: `lawn_mower.py`**

```python
"""Lawn mower-Plattform für Navimow Simple."""
from __future__ import annotations

from homeassistant.components.lawn_mower import (
    LawnMowerActivity,
    LawnMowerEntity,
    LawnMowerEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NavimowConfigEntry
from .api import state_to_activity
from .const import DOMAIN
from .coordinator import NavimowCoordinator

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NavimowConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([NavimowLawnMower(entry.runtime_data.coordinator)])


class NavimowLawnMower(CoordinatorEntity[NavimowCoordinator], LawnMowerEntity):
    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = (
        LawnMowerEntityFeature.START_MOWING
        | LawnMowerEntityFeature.PAUSE
        | LawnMowerEntityFeature.DOCK
    )

    def __init__(self, coordinator: NavimowCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_sn}_mower"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_sn)},
            name=coordinator.device_name,
            manufacturer="Segway Navimow",
            model="i105",
            serial_number=coordinator.device_sn,
        )

    @property
    def activity(self) -> LawnMowerActivity | None:
        data = self.coordinator.data
        if not data:
            return None
        return state_to_activity(data.get("state"))

    async def _send(self, action: str) -> None:
        await self.coordinator.client.async_send_command(
            self.coordinator.device_sn, action
        )
        await self.coordinator.async_request_refresh()

    async def async_start_mowing(self) -> None:
        # Start aus PAUSED behandelt die API als Resume (Spike bestätigt
        # gleichen oder eigenen Befehl; ggf. "resume" in COMMANDS ergänzen).
        await self._send("start")

    async def async_pause(self) -> None:
        await self._send("pause")

    async def async_dock(self) -> None:
        await self._send("dock")
```

- [ ] **Step 4: Run → PASS**

Run: `uv run --group test pytest tests/test_lawn_mower.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add custom_components/navimow_simple/lawn_mower.py tests/test_lawn_mower.py
git commit -m "feat: lawn_mower-Entity (Activity-Mapping, Start/Pause/Dock)"
git push
```

---

## Task 15: `sensor.py`

**Files:**
- Create: `custom_components/navimow_simple/sensor.py`
- Test: `tests/test_sensor.py`

- [ ] **Step 1: Failing test**

`tests/test_sensor.py`:

```python
from unittest.mock import patch

import pytest
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.navimow_simple.const import DOMAIN


@pytest.mark.asyncio
async def test_battery_and_status_sensors(hass: HomeAssistant):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="SN1",
        data={
            CONF_EMAIL: "u@example.com",
            CONF_PASSWORD: "pw",
            "device_sn": "SN1",
            "device_name": "Mäher",
        },
    )
    entry.add_to_hass(hass)
    status = {
        "vehicleState": "isDocked",
        "capacityRemaining": [{"unit": "PERCENTAGE", "rawValue": 73}],
    }
    with patch(
        "custom_components.navimow_simple.NavimowClient.async_get_status",
        return_value=status,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.maher_battery").state == "73"
    assert hass.states.get("sensor.maher_status").state == "isDocked"
```

- [ ] **Step 2: Run → FAIL**

Run: `uv run --group test pytest tests/test_sensor.py -v`
Expected: FAIL (sensor-Plattform fehlt).

- [ ] **Step 3: `sensor.py`**

```python
"""Sensor-Plattform: Akku-% und Status-Text."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NavimowConfigEntry
from .const import DOMAIN
from .coordinator import NavimowCoordinator

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class NavimowSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], Any]


SENSORS: tuple[NavimowSensorDescription, ...] = (
    NavimowSensorDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda d: d.get("battery"),
    ),
    NavimowSensorDescription(
        key="status",
        translation_key="status",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("state"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NavimowConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        NavimowSensor(coordinator, desc) for desc in SENSORS
    )


class NavimowSensor(CoordinatorEntity[NavimowCoordinator], SensorEntity):
    _attr_has_entity_name = True
    entity_description: NavimowSensorDescription

    def __init__(
        self,
        coordinator: NavimowCoordinator,
        description: NavimowSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_sn}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_sn)},
            name=coordinator.device_name,
            manufacturer="Segway Navimow",
            model="i105",
            serial_number=coordinator.device_sn,
        )

    @property
    def native_value(self) -> Any:
        if not self.coordinator.data:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
```

> **Hinweis:** Der `battery`-Sensor erhält über `device_class=battery` automatisch den Namen „Battery"; der Status-Sensor braucht einen Eintrag `entity.sensor.status.name` in `strings.json`/Translations (Task 16), sonst heißt die Entität nur „Status" via `translation_key`. Falls die Test-Entity-ID abweicht, mit `hass.states.async_entity_ids()` prüfen und anpassen.

- [ ] **Step 4: Run → PASS**

Run: `uv run --group test pytest tests/test_sensor.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add custom_components/navimow_simple/sensor.py tests/test_sensor.py
git commit -m "feat: Akku- und Status-Sensoren"
git push
```

---

## Task 16: Translations + `diagnostics.py`

**Files:**
- Create: `custom_components/navimow_simple/translations/de.json`, `translations/en.json`
- Create: `custom_components/navimow_simple/diagnostics.py`
- Test: `tests/test_diagnostics.py`

- [ ] **Step 1: Translations**

`translations/de.json` = Inhalt von `strings.json` (Task 12/13) **plus** Entity-Namen:

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Navimow Simple",
        "description": "Melde dich mit deinem Segway-Konto an.",
        "data": { "email": "E-Mail", "password": "Passwort" }
      },
      "reauth_confirm": {
        "title": "Navimow erneut anmelden",
        "description": "Bitte Zugangsdaten erneut eingeben.",
        "data": { "email": "E-Mail", "password": "Passwort" }
      }
    },
    "error": {
      "invalid_auth": "Anmeldung fehlgeschlagen.",
      "cannot_connect": "Verbindung fehlgeschlagen.",
      "no_devices": "Kein Mäher gefunden."
    },
    "abort": {
      "already_configured": "Gerät ist bereits eingerichtet.",
      "reauth_successful": "Erneute Anmeldung erfolgreich."
    }
  },
  "entity": {
    "sensor": { "status": { "name": "Status" } }
  }
}
```

`translations/en.json` analog mit englischen Texten (Status → „Status", Fehlertexte übersetzt). `strings.json` um denselben `entity`-Block ergänzen.

- [ ] **Step 2: Failing test (Diagnostics redacted)**

`tests/test_diagnostics.py`:

```python
from unittest.mock import patch

import pytest
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.navimow_simple.const import DOMAIN
from custom_components.navimow_simple.diagnostics import (
    async_get_config_entry_diagnostics,
)


@pytest.mark.asyncio
async def test_diagnostics_redacts_password(hass: HomeAssistant):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="SN1",
        data={
            CONF_EMAIL: "u@example.com",
            CONF_PASSWORD: "secret",
            "device_sn": "SN1",
            "device_name": "Mäher",
        },
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.navimow_simple.NavimowClient.async_get_status",
        return_value={"vehicleState": "isDocked", "capacityRemaining": []},
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        diag = await async_get_config_entry_diagnostics(hass, entry)

    assert "secret" not in str(diag)
    assert diag["data"]["state"] == "isDocked"
```

- [ ] **Step 3: Run → FAIL**

Run: `uv run --group test pytest tests/test_diagnostics.py -v`
Expected: FAIL (`diagnostics` fehlt).

- [ ] **Step 4: `diagnostics.py`**

```python
"""Diagnostics-Snapshot (redacted)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from . import NavimowConfigEntry

TO_REDACT = {CONF_EMAIL, CONF_PASSWORD, "device_sn", "serial_number"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: NavimowConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data.coordinator
    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "data": coordinator.data,
    }
```

- [ ] **Step 5: Run → PASS**

Run: `uv run --group test pytest tests/test_diagnostics.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add custom_components/navimow_simple/translations custom_components/navimow_simple/strings.json custom_components/navimow_simple/diagnostics.py tests/test_diagnostics.py
git commit -m "feat: Translations (de/en) + redacted Diagnostics"
git push
```

---

## Task 17: HACS-Dateien + Branding + Lint/Type-Gate

**Files:**
- Create: `hacs.json`, `LICENSE`, `.gitignore` (existiert), README-Erweiterung

- [ ] **Step 1: `hacs.json`**

```json
{
  "name": "Navimow Simple",
  "homeassistant": "2026.3.0",
  "render_readme": true
}
```

- [ ] **Step 2: `LICENSE` (GPL-3.0)**

Run: `cd /tmp/navimow-i105-ha && curl -fsSL https://www.gnu.org/licenses/gpl-3.0.txt -o LICENSE && head -1 LICENSE`
Expected: `                    GNU GENERAL PUBLIC LICENSE`

- [ ] **Step 3: README um Install/Removal/Attribution erweitern**

In `README.md` ergänzen: HACS-Custom-Repo-Installation (URL `https://github.com/Schnabel80/navimow-i105-ha`, Kategorie Integration), Entfernen (Integration löschen → HACS entfernen), Konfigurationsparameter (E-Mail/Passwort), und GPL-Attribution an NavimowHA.

- [ ] **Step 4: Voller Lint/Type/Test-Gate**

Run:
```bash
cd /tmp/navimow-i105-ha
uv run --group lint ruff check .
uv run --group lint ruff format --check .
uv run --group typecheck ty check custom_components
uv run --group test pytest -q
```
Expected: ruff clean, ty clean (oder dokumentierte Ignores), alle Tests grün.

- [ ] **Step 5: Commit**

```bash
git add hacs.json LICENSE README.md
git commit -m "chore: HACS-Manifest, GPL-3.0-LICENSE, README-Anleitung"
git push
```

---

## Task 18: Coverage ≥95 % + CI

**Files:**
- Create: `.github/workflows/ci.yml`
- Modify: `pyproject.toml` (coverage-Konfig)

- [ ] **Step 1: Coverage messen**

Run: `cd /tmp/navimow-i105-ha && uv run --group test pytest --cov=custom_components/navimow_simple --cov-report=term-missing`
Expected: Bericht. Lücken mit gezielten Tests schließen (z.B. `cannot_connect`-Pfad im Config-Flow, `no_devices`, Coordinator-`UpdateFailed`, Sensor-`native_value=None`).

- [ ] **Step 2: Fehlende Pfade testen**

Pro identifizierter Lücke einen Test ergänzen (Beispiel `no_devices`):

```python
@pytest.mark.asyncio
async def test_user_flow_no_devices(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    with patch(
        "custom_components.navimow_simple.config_flow.NavimowClient.async_get_devices",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: "u@example.com", CONF_PASSWORD: "pw"},
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "no_devices"
```

Wiederholen bis `--cov` ≥ 95 %.

- [ ] **Step 3: CI-Workflow**

`.github/workflows/ci.yml`:

```yaml
name: CI
on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: home-assistant/actions/hassfest@master
      - uses: hacs/action@main
        with:
          category: integration

  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: astral-sh/setup-uv@v6
        with:
          enable-cache: true
      - run: uv sync --group dev
      - run: uv run --group lint ruff check .
      - run: uv run --group lint ruff format --check .
      - run: uv run --group test pytest --cov=custom_components/navimow_simple --cov-fail-under=95
```

- [ ] **Step 4: Lokaler Gate + Commit**

Run:
```bash
cd /tmp/navimow-i105-ha
uv run --group test pytest --cov=custom_components/navimow_simple --cov-fail-under=95
```
Expected: PASS, Coverage ≥ 95 %.

```bash
git add .github/workflows/ci.yml pyproject.toml tests
git commit -m "ci: hassfest + HACS + pytest, Coverage-Gate 95%"
git push
```

- [ ] **Step 5: Verifizieren dass CI grün ist**

Run: `gh run watch` (oder `gh run list --limit 1`)
Expected: alle Jobs grün.

---

## Definition of Done

- [ ] Spike-Findings dokumentiert; `STATE_MAP`/`COMMANDS`/`SILENT_PASSWORD_LOGIN` mit echten Werten gefüllt.
- [ ] `lawn_mower`-Entity zeigt Status, steuert Start/Pause/Dock am echten i105 (Docker-Test).
- [ ] Akku-% + Status-Sensor korrekt.
- [ ] Reauth-Flow funktioniert.
- [ ] `ruff` + `ty` clean, Tests ≥ 95 % Coverage, CI grün.
- [ ] Erste Beta `v0.1.0b1` als GitHub-Pre-Release (Workflow analog weather_mow).
- [ ] Keine personenbezogenen IDs in Repo/History.

---

## Self-Review-Notiz (Autor)

- **Spec-Abdeckung:** Token-Lock (T8/9), 4003-Retry (T6), kein MQTT (Architektur durchgängig), lawn_mower+Sensoren (T14/15), Reauth (T13), Diagnostics (T16), Bronze/Silver-Regeln (has_entity_name, unique_id, runtime_data, PARALLEL_UPDATES, config-flow-tests, reauth, ≥95%). ✓
- **Spike-Abhängigkeiten** isoliert in `const.py`; alle Tests prüfen Mechanik, nicht Magiewerte. ✓
- **Bekannte Abweichung:** `state_to_activity` importiert `LawnMowerActivity` (HA-Enum) in `api.py` → `api.py` ist damit nicht 100 % HA-frei. Bewusst akzeptiert (reiner Enum). Alternative: Funktion nach `coordinator.py` ziehen, falls strikte HA-Reinheit gefordert wird.
