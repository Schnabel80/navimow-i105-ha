"""DataUpdateCoordinator (90 s Poll, einziger Token-Nutzer)."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import NavimowAuthError, NavimowError
from .const import (
    DOMAIN,
    POST_COMMAND_REFRESH_DELAY_SECONDS,
    UPDATE_INTERVAL_SECONDS,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .api import NavimowClient

_LOGGER = logging.getLogger(__name__)


def _extract_battery(status: dict[str, Any]) -> int | None:
    cap = status.get("capacityRemaining")
    if not isinstance(cap, list) or not cap:
        return None
    for item in cap:
        if isinstance(item, dict) and str(item.get("unit", "")).upper() == (
            "PERCENTAGE"
        ):
            raw = item.get("rawValue")
            return int(raw) if raw is not None else None
    raw = cap[0].get("rawValue") if isinstance(cap[0], dict) else None
    return int(raw) if raw is not None else None


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

    def async_schedule_post_command_refresh(self) -> None:
        """Plant ein einmaliges Refresh ~10 s nach einem Steuerbefehl."""

        async def _refresh(_now) -> None:
            await self.async_request_refresh()

        async_call_later(
            self.hass, POST_COMMAND_REFRESH_DELAY_SECONDS, _refresh
        )

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
