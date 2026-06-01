from datetime import timedelta
from unittest.mock import AsyncMock, patch

import homeassistant.util.dt as dt_util
import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.navimow_simple.const import DOMAIN

DEVICES = [{"id": "SN1", "name": "Maeher", "model": "i105"}]
STATUS = {"vehicleState": "isDocked", "capacityRemaining": []}


async def _setup(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
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
    entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.navimow_simple.NavimowClient.async_get_devices",
            return_value=DEVICES,
        ),
        patch(
            "custom_components.navimow_simple.NavimowClient.async_get_status",
            return_value=STATUS,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_stop_and_resume_buttons(hass: HomeAssistant):
    await _setup(hass)
    buttons = [
        s.entity_id for s in hass.states.async_all() if s.domain == "button"
    ]
    assert len(buttons) == 2

    for action in ("stop", "resume"):
        entity_id = next(b for b in buttons if action in b)
        with (
            patch(
                "custom_components.navimow_simple."
                "NavimowClient.async_send_command",
                new=AsyncMock(),
            ) as send,
            patch(
                "custom_components.navimow_simple."
                "NavimowClient.async_get_status",
                return_value=STATUS,
            ),
        ):
            await hass.services.async_call(
                "button",
                "press",
                {"entity_id": entity_id},
                blocking=True,
            )
            # Verzögerten 10-s-Timer noch im Patch-Kontext abarbeiten,
            # damit kein Timer den Patch überlebt (lingering timer).
            async_fire_time_changed(
                hass, dt_util.utcnow() + timedelta(seconds=11)
            )
            await hass.async_block_till_done()
        send.assert_awaited_once()
        assert send.await_args.args[1] == action
