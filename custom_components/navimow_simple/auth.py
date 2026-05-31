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
