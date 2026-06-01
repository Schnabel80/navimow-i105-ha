from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.navimow_simple.const import DOMAIN
from custom_components.navimow_simple.diagnostics import (
    async_get_config_entry_diagnostics,
)


@pytest.mark.asyncio
async def test_diagnostics_redacts_secrets(hass: HomeAssistant):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "SECRET_AT",
                "refresh_token": "SECRET_RT",
                "expires_at": 9999999999,
                "expires_in": 3600,
                "token_type": "Bearer",
            },
        },
    )
    entry.add_to_hass(hass)
    status = {
        "id": "SECRET_DEVICE_ID",
        "vehicleState": "isDocked",
        "capacityRemaining": [{"unit": "PERCENTAGE", "rawValue": 50}],
    }
    with (
        patch(
            "custom_components.navimow_simple.NavimowClient.async_get_devices",
            return_value=[{"id": "SECRET_DEVICE_ID", "name": "Maeher"}],
        ),
        patch(
            "custom_components.navimow_simple.NavimowClient.async_get_status",
            return_value=status,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        diag = await async_get_config_entry_diagnostics(hass, entry)

    blob = str(diag)
    assert "SECRET_AT" not in blob
    assert "SECRET_RT" not in blob
    assert "SECRET_DEVICE_ID" not in blob
    assert diag["data"]["state"] == "isDocked"
