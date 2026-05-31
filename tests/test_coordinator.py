import pytest

from custom_components.navimow_simple.coordinator import NavimowCoordinator


class _FakeClient:
    def __init__(self, status):
        self._status = status

    async def async_get_status(self, sn):
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
