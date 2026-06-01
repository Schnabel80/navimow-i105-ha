"""Diagnostics-Snapshot (redacted) für Navimow Simple."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from . import NavimowConfigEntry

TO_REDACT = {
    "token",
    "access_token",
    "refresh_token",
    "id",
    "serial_number",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: NavimowConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data.coordinator
    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "device_name": coordinator.device_name,
        "data": async_redact_data(coordinator.data or {}, TO_REDACT),
    }
