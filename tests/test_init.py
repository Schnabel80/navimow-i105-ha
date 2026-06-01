from unittest.mock import patch

import pytest
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


@pytest.mark.asyncio
async def test_setup_and_unload(hass: HomeAssistant):
    entry = _entry()
    entry.add_to_hass(hass)
    status = {
        "vehicleState": "isDocked",
        "capacityRemaining": [{"unit": "PERCENTAGE", "rawValue": 50}],
    }
    # LAWN_MOWER/SENSOR platform modules are built in a later task; here we
    # exercise only the OAuth/setup/discovery path and stub the forward.
    with (
        patch(
            "custom_components.navimow_simple.NavimowClient.async_get_devices",
            return_value=[{"id": "SN1", "name": "Mäher", "model": "i105"}],
        ),
        patch(
            "custom_components.navimow_simple.NavimowClient.async_get_status",
            return_value=status,
        ),
        patch(
            "homeassistant.config_entries.ConfigEntries."
            "async_forward_entry_setups",
            return_value=None,
        ),
        patch(
            "homeassistant.config_entries.ConfigEntries."
            "async_unload_platforms",
            return_value=True,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.runtime_data.coordinator.data["battery"] == 50
        assert await hass.config_entries.async_unload(entry.entry_id)
