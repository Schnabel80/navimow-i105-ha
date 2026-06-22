"""HA-unabhängiger HTTP-Client für die Navimow smarthome-openapi."""

from __future__ import annotations

import uuid
from typing import Any, Protocol

import aiohttp

from .const import (
    ALREADY_IN_STATE,
    AUTH_ERROR_CODES,
    BASE_URL,
    CIRCUIT_BREAKER_CODES,
    COMMANDS,
    PATH_AUTH_LIST,
    PATH_COMMANDS,
    PATH_STATUS,
    STATE_MAP,
    SUCCESS_CODE,
)


class NavimowError(Exception):
    """Basis-Fehler."""


class NavimowAuthError(NavimowError):
    """Token ungültig/abgelaufen (4003 / TOKEN_EMPTY)."""


class NavimowApiError(NavimowError):
    """Sonstiger API-/HTTP-Fehler."""


class NavimowRateLimitError(NavimowApiError):
    """Gateway drosselt (Circuit Breaker, 4001) — transient, Backoff."""


class TokenSource(Protocol):
    async def async_get_valid_token(
        self, force_refresh: bool = False
    ) -> str: ...


class NavimowClient:
    """Drei REST-Calls gegen die smarthome-openapi (Envelope code==1)."""

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
    ) -> dict[str, Any]:
        """Sendet Request, prüft Envelope, gibt data.payload zurück."""
        token = await self._tokens.async_get_valid_token(
            force_refresh=_retried
        )
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
                body = await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            raise NavimowApiError(f"HTTP-Fehler bei {path}: {err}") from err

        code = body.get("code") if isinstance(body, dict) else None
        if status in (401, 403) or (str(code) in AUTH_ERROR_CODES):
            if not _retried:
                return await self._request(
                    method, path, json=json, _retried=True
                )
            raise NavimowAuthError(f"Auth abgelehnt bei {path} (code={code})")
        if code != SUCCESS_CODE:
            desc = body.get("desc") if isinstance(body, dict) else None
            if str(code) in CIRCUIT_BREAKER_CODES:
                raise NavimowRateLimitError(
                    f"API gedrosselt bei {path}: code={code} desc={desc}"
                )
            raise NavimowApiError(
                f"API-Fehler bei {path}: code={code} desc={desc}"
            )
        return body.get("data", {}).get("payload", {})

    async def async_get_devices(self) -> list[dict[str, Any]]:
        payload = await self._request("GET", PATH_AUTH_LIST)
        return payload.get("devices", [])

    async def async_get_status(self, device_id: str) -> dict[str, Any]:
        payload = await self._request(
            "POST", PATH_STATUS, json={"devices": [{"id": device_id}]}
        )
        devices = payload.get("devices", [])
        if not devices:
            raise NavimowApiError(f"Kein Status für Gerät {device_id}")
        return devices[0]

    async def async_send_command(self, device_id: str, action: str) -> None:
        body = {
            "commands": [
                {
                    "devices": [{"id": device_id}],
                    "execution": COMMANDS[action],
                }
            ]
        }
        payload = await self._request("POST", PATH_COMMANDS, json=body)
        for result in payload.get("commands", []):
            if (
                result.get("status") == "ERROR"
                and result.get("errorCode") != ALREADY_IN_STATE
            ):
                raise NavimowApiError(
                    f"Befehl '{action}' fehlgeschlagen: "
                    f"{result.get('errorCode')}"
                )


def state_to_activity(raw: str | None):
    """vehicleState-String -> LawnMowerActivity, unbekannt -> ERROR."""
    from homeassistant.components.lawn_mower import LawnMowerActivity

    if raw is None:
        return LawnMowerActivity.ERROR
    return STATE_MAP.get(raw, LawnMowerActivity.ERROR)
