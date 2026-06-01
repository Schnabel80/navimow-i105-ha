import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.navimow_simple.api import (
    NavimowAuthError,
    NavimowError,
)
from custom_components.navimow_simple.coordinator import (
    NavimowCoordinator,
    _extract_battery,
)


class _FakeClient:
    def __init__(self, status=None, *, error=None):
        self._status = status
        self._error = error

    async def async_get_status(self, sn):
        if self._error is not None:
            raise self._error
        return self._status


@pytest.mark.asyncio
async def test_update_maps_state_and_battery(hass):
    client = _FakeClient(
        {
            "vehicleState": "isRunning",
            "capacityRemaining": [{"unit": "PERCENTAGE", "rawValue": 73}],
        }
    )
    coord = NavimowCoordinator(
        hass, client, device_sn="SN1", device_name="Mäher"
    )
    data = await coord._async_update_data()
    assert data["state"] == "isRunning"
    assert data["battery"] == 73


@pytest.mark.asyncio
async def test_update_auth_error_raises_auth_failed(hass):
    coord = NavimowCoordinator(
        hass,
        _FakeClient(error=NavimowAuthError("bad token")),
        device_sn="SN1",
        device_name="Mäher",
    )
    with pytest.raises(ConfigEntryAuthFailed):
        await coord._async_update_data()


@pytest.mark.asyncio
async def test_update_api_error_raises_update_failed(hass):
    coord = NavimowCoordinator(
        hass,
        _FakeClient(error=NavimowError("api down")),
        device_sn="SN1",
        device_name="Mäher",
    )
    with pytest.raises(UpdateFailed):
        await coord._async_update_data()


def test_extract_battery_none_when_empty():
    assert _extract_battery({"capacityRemaining": []}) is None
    assert _extract_battery({}) is None


def test_extract_battery_fallback_to_first_item():
    # Kein PERCENTAGE-Eintrag → Fallback auf erstes Item.
    status = {"capacityRemaining": [{"unit": "MINUTES", "rawValue": 42}]}
    assert _extract_battery(status) == 42


def test_extract_battery_fallback_non_dict_first_item():
    status = {"capacityRemaining": ["weird"]}
    assert _extract_battery(status) is None
