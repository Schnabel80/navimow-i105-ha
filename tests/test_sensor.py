from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.navimow_simple.const import DOMAIN


@pytest.mark.asyncio
async def test_battery_and_status_sensors(hass: HomeAssistant):
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
    status = {
        "vehicleState": "isDocked",
        "capacityRemaining": [{"unit": "PERCENTAGE", "rawValue": 73}],
    }
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

    sensors = {
        s.entity_id: s.state
        for s in hass.states.async_all()
        if s.domain == "sensor"
    }
    # genau zwei Sensoren; Akku=73, Status=isDocked
    assert any(v == "73" for v in sensors.values())
    assert any(v == "isDocked" for v in sensors.values())
