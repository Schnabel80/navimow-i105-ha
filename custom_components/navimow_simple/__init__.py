"""Navimow Simple integration (Browser-OAuth, HTTP-Polling, kein MQTT)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
)
from homeassistant.helpers import (
    config_entry_oauth2_flow,
)
from homeassistant.helpers import (
    config_validation as cv,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NavimowAuthError, NavimowClient, NavimowError
from .auth import NavimowOAuth2Implementation, OAuth2TokenSource
from .const import DOMAIN
from .coordinator import NavimowCoordinator

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.LAWN_MOWER,
    Platform.SENSOR,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass
class NavimowRuntime:
    coordinator: NavimowCoordinator
    client: NavimowClient


type NavimowConfigEntry = ConfigEntry[NavimowRuntime]


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, NavimowOAuth2Implementation(hass)
    )
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: NavimowConfigEntry
) -> bool:
    implementation = await (
        config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    oauth_session = config_entry_oauth2_flow.OAuth2Session(
        hass, entry, implementation
    )
    try:
        await oauth_session.async_ensure_token_valid()
    except Exception as err:
        raise ConfigEntryAuthFailed(str(err)) from err

    client = NavimowClient(
        async_get_clientsession(hass), OAuth2TokenSource(oauth_session)
    )
    try:
        devices = await client.async_get_devices()
    except NavimowAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except NavimowError as err:
        raise ConfigEntryNotReady(str(err)) from err
    if not devices:
        raise ConfigEntryNotReady("Keine Navimow-Geräte gefunden")

    device = devices[0]
    coordinator = NavimowCoordinator(
        hass,
        client,
        device_sn=device["id"],
        device_name=device.get("name", "Navimow"),
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = NavimowRuntime(coordinator, client)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: NavimowConfigEntry
) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
