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

# --- OAuth2 ------------------------------------------------------------
OAUTH2_AUTHORIZE: Final = "https://navimow-h5-fra.willand.com/smartHome/login"
OAUTH2_TOKEN: Final = (
    "https://navimow-fra.ninebot.com/openapi/oauth/getAccessToken"
)

# Erfolgscode des smarthome-Envelopes (NICHT 0/200).
SUCCESS_CODE: Final = 1
# Command-Result-Code "schon im Zielzustand" -> als Erfolg werten.
ALREADY_IN_STATE: Final = "alreadyInState"

# --- Polling -----------------------------------------------------------
UPDATE_INTERVAL_SECONDS: Final = 90
TOKEN_EXPIRY_BUFFER_SECONDS: Final = 60

# Verzögertes Refresh nach einem Steuerbefehl
# (Mäher braucht Zeit zum Umsetzen).
POST_COMMAND_REFRESH_DELAY_SECONDS: Final = 10

# --- Fehlercodes (Auth) ------------------------------------------------
AUTH_ERROR_CODES: Final = frozenset({"4003", "TOKEN_EMPTY"})

# --- Drosselung / Circuit Breaker --------------------------------------
# Das OpenAPI-Gateway sperrt einen Endpoint nach wiederholten Upstream-
# Fehlern temporär (code 4001 "url Circuit Breaker"). Solange das anliegt,
# pollt die Integration deutlich seltener (BACKOFF_INTERVAL_SECONDS), damit
# sie den Breaker nicht durch den normalen 90-s-Takt selbst warm hält.
CIRCUIT_BREAKER_CODES: Final = frozenset({"4001"})
BACKOFF_INTERVAL_SECONDS: Final = 600

# --- vehicleState -> LawnMowerActivity (autoritativ aus SDK) -----------
STATE_MAP: Final[dict[str, LawnMowerActivity]] = {
    "isDocked": LawnMowerActivity.DOCKED,
    "isIdle": LawnMowerActivity.DOCKED,
    "isIdel": LawnMowerActivity.DOCKED,
    "Self-Checking": LawnMowerActivity.DOCKED,
    "Self-checking": LawnMowerActivity.DOCKED,
    "isMapping": LawnMowerActivity.MOWING,
    "isRunning": LawnMowerActivity.MOWING,
    "isPaused": LawnMowerActivity.PAUSED,
    "inSoftwareUpdate": LawnMowerActivity.PAUSED,
    "isDocking": LawnMowerActivity.RETURNING,
    "Error": LawnMowerActivity.ERROR,
    "error": LawnMowerActivity.ERROR,
    "isLifted": LawnMowerActivity.ERROR,
    "Offline": LawnMowerActivity.ERROR,
    "offline": LawnMowerActivity.ERROR,
}

# --- Command-Payloads (Google-Smart-Home-Grammatik) --------------------
# action -> execution-Objekt (command + optional params).
COMMANDS: Final[dict[str, dict]] = {
    "start": {
        "command": "action.devices.commands.StartStop",
        "params": {"on": True},
    },
    "stop": {
        "command": "action.devices.commands.StartStop",
        "params": {"on": False},
    },
    "pause": {
        "command": "action.devices.commands.PauseUnpause",
        "params": {"on": False},
    },
    "resume": {
        "command": "action.devices.commands.PauseUnpause",
        "params": {"on": True},
    },
    "dock": {"command": "action.devices.commands.Dock"},
}
