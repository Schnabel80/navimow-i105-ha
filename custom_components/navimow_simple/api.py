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
    STATE_MAP,
)


class NavimowError(Exception):
    """Basis-Fehler."""


class NavimowAuthError(NavimowError):
    """Token ungültig/abgelaufen (4003 / TOKEN_EMPTY)."""


class NavimowApiError(NavimowError):
    """Sonstiger API-/HTTP-Fehler."""


class TokenSource(Protocol):
    async def async_get_valid_token(
        self, force_refresh: bool = False
    ) -> str: ...


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
                payload = await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            raise NavimowApiError(f"HTTP-Fehler bei {path}: {err}") from err

        code = str(payload.get("code")) if isinstance(payload, dict) else None
        if status in (401, 403) or (code in AUTH_ERROR_CODES):
            if not _retried:
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


def state_to_activity(raw: str | None):
    """vehicleState-String -> LawnMowerActivity, unbekannt -> ERROR."""
    from homeassistant.components.lawn_mower import LawnMowerActivity

    if raw is None:
        return LawnMowerActivity.ERROR
    return STATE_MAP.get(raw, LawnMowerActivity.ERROR)
