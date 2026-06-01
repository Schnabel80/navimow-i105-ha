"""Button-Plattform: Stopp und Fortsetzen für Navimow Simple."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.button import (
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NavimowCoordinator

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import NavimowConfigEntry

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class NavimowButtonDescription(ButtonEntityDescription):
    action: str


BUTTONS: tuple[NavimowButtonDescription, ...] = (
    NavimowButtonDescription(
        key="stop", translation_key="stop", action="stop"
    ),
    NavimowButtonDescription(
        key="resume", translation_key="resume", action="resume"
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NavimowConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities(NavimowButton(coordinator, d) for d in BUTTONS)


class NavimowButton(CoordinatorEntity[NavimowCoordinator], ButtonEntity):
    _attr_has_entity_name = True
    entity_description: NavimowButtonDescription

    def __init__(
        self,
        coordinator: NavimowCoordinator,
        description: NavimowButtonDescription,
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

    async def async_press(self) -> None:
        await self.coordinator.client.async_send_command(
            self.coordinator.device_sn, self.entity_description.action
        )
        await self.coordinator.async_request_refresh()
        self.coordinator.async_schedule_post_command_refresh()
