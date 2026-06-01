"""Lawn mower-Plattform für Navimow Simple."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.lawn_mower import (
    LawnMowerActivity,
    LawnMowerEntity,
    LawnMowerEntityFeature,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import state_to_activity
from .const import DOMAIN
from .coordinator import NavimowCoordinator

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import NavimowConfigEntry

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NavimowConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([NavimowLawnMower(entry.runtime_data.coordinator)])


class NavimowLawnMower(CoordinatorEntity[NavimowCoordinator], LawnMowerEntity):
    """Navimow i105 als lawn_mower-Entity."""

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
        # Start aus PAUSED behandelt die API über StartStop/PauseUnpause
        # einheitlich; wir senden "start".
        await self._send("start")

    async def async_pause(self) -> None:
        await self._send("pause")

    async def async_dock(self) -> None:
        await self._send("dock")
