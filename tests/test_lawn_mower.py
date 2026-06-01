from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.lawn_mower import LawnMowerActivity
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.navimow_simple.const import DOMAIN


def _entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "at",
                "refresh_token": "rt",
                "expires_at": 9999999999,
                "expires_in": 3600,
                "token_type": "Bearer",
            },
        },
    )


async def _setup(hass: HomeAssistant, status: dict) -> None:
    entry = _entry()
    entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.navimow_simple.NavimowClient.async_get_devices",
            return_value=[{"id": "SN1", "name": "Maeher", "model": "i105"}],
        ),
        patch(
            "custom_components.navimow_simple.NavimowClient.async_get_status",
            return_value=status,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_activity_mowing(hass: HomeAssistant):
    await _setup(hass, {"vehicleState": "isRunning", "capacityRemaining": []})
    states = [s for s in hass.states.async_all() if s.domain == "lawn_mower"]
    assert len(states) == 1
    assert states[0].state == LawnMowerActivity.MOWING


@pytest.mark.asyncio
async def test_start_calls_send_command(hass: HomeAssistant):
    await _setup(hass, {"vehicleState": "isDocked", "capacityRemaining": []})
    entity_id = next(
        s.entity_id
        for s in hass.states.async_all()
        if s.domain == "lawn_mower"
    )
    with (
        patch(
            "custom_components.navimow_simple.NavimowClient."
            "async_send_command",
            new=AsyncMock(),
        ) as send,
        patch(
            "custom_components.navimow_simple.NavimowClient.async_get_status",
            return_value={
                "vehicleState": "isRunning",
                "capacityRemaining": [],
            },
        ),
    ):
        await hass.services.async_call(
            "lawn_mower",
            "start_mowing",
            {"entity_id": entity_id},
            blocking=True,
        )
    send.assert_awaited_once()
    assert send.await_args.args[1] == "start"
