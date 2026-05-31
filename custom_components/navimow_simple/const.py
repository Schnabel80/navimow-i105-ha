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
# Vom Spike bestätigt (authList/getVehicleStatus).
DEVICE_SN_KEY: Final = "deviceSn"

# --- Polling -----------------------------------------------------------
UPDATE_INTERVAL_SECONDS: Final = 90
TOKEN_EXPIRY_BUFFER_SECONDS: Final = 60

# --- Fehlercodes (Auth) ------------------------------------------------
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
# Exakte Body-Schemata aus dem Spike. Platzhalter-Form, wird 1:1 ersetzt.
COMMANDS: Final[dict[str, dict]] = {
    "start": {"command": "start"},
    "pause": {"command": "pause"},
    "dock": {"command": "dock"},
}

# Auth-Strategie aus Spike: True = stiller E-Mail+PW-Login (Weg A).
SILENT_PASSWORD_LOGIN: Final = True
