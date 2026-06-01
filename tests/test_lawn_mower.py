from datetime import timedelta
from unittest.mock import AsyncMock, patch

import homeassistant.util.dt as dt_util
import pytest
from homeassistant.components.lawn_mower import LawnMowerActivity
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

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


def _entity_id(hass: HomeAssistant) -> str:
    return next(
        s.entity_id
        for s in hass.states.async_all()
        if s.domain == "lawn_mower"
    )


async def _call_and_capture_action(hass: HomeAssistant, service: str) -> str:
    entity_id = _entity_id(hass)
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
            service,
            {"entity_id": entity_id},
            blocking=True,
        )
        # Verzögerten 10-s-Timer noch im Patch-Kontext abarbeiten,
        # damit kein Timer den Patch überlebt (lingering timer).
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=11))
        await hass.async_block_till_done()
    send.assert_awaited_once()
    return send.await_args.args[1]


@pytest.mark.asyncio
async def test_start_calls_send_command(hass: HomeAssistant):
    await _setup(hass, {"vehicleState": "isDocked", "capacityRemaining": []})
    assert await _call_and_capture_action(hass, "start_mowing") == "start"


@pytest.mark.asyncio
async def test_pause_calls_send_command(hass: HomeAssistant):
    await _setup(hass, {"vehicleState": "isRunning", "capacityRemaining": []})
    assert await _call_and_capture_action(hass, "pause") == "pause"


@pytest.mark.asyncio
async def test_dock_calls_send_command(hass: HomeAssistant):
    await _setup(hass, {"vehicleState": "isRunning", "capacityRemaining": []})
    assert await _call_and_capture_action(hass, "dock") == "dock"


@pytest.mark.asyncio
async def test_command_triggers_delayed_refresh(hass: HomeAssistant):
    await _setup(hass, {"vehicleState": "isDocked", "capacityRemaining": []})
    entity_id = _entity_id(hass)
    with (
        patch(
            "custom_components.navimow_simple.NavimowClient."
            "async_send_command",
            new=AsyncMock(),
        ),
        patch(
            "custom_components.navimow_simple.NavimowClient.async_get_status",
            new=AsyncMock(
                return_value={
                    "vehicleState": "isRunning",
                    "capacityRemaining": [],
                }
            ),
        ) as status,
    ):
        await hass.services.async_call(
            "lawn_mower",
            "start_mowing",
            {"entity_id": entity_id},
            blocking=True,
        )
        immediate = status.await_count
        # 10-s-Timer feuern (innerhalb des Patches!)
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=11))
        await hass.async_block_till_done()
        assert status.await_count > immediate  # verzögertes Refresh kam


@pytest.mark.asyncio
async def test_activity_none_when_no_data(hass: HomeAssistant):
    from custom_components.navimow_simple.coordinator import (
        NavimowCoordinator,
    )
    from custom_components.navimow_simple.lawn_mower import NavimowLawnMower

    coord = NavimowCoordinator(
        hass, object(), device_sn="SN1", device_name="Maeher"
    )
    coord.data = None
    entity = NavimowLawnMower(coord)
    assert entity.activity is None
