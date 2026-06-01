from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.navimow_simple.const import (
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
)

REDIRECT_URI = "https://example.com/auth/external/callback"

DEVICES = [{"id": "SN1", "name": "Maeher", "model": "i105"}]
STATUS = {"vehicleState": "isDocked", "capacityRemaining": []}


@pytest.fixture
async def setup_credentials(hass: HomeAssistant):
    assert await async_setup_component(hass, DOMAIN, {})
    return True


def _entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "old",
                "refresh_token": "old_rt",
                "expires_at": 9999999999,
                "expires_in": 3600,
                "token_type": "Bearer",
            },
        },
    )


async def _drive_oauth_to_token(
    hass: HomeAssistant,
    hass_client_no_auth,
    aioclient_mock,
    result: dict,
) -> dict:
    """External-step → callback → token-exchange; returns flow result."""
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {"flow_id": result["flow_id"], "redirect_uri": REDIRECT_URI},
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert result["url"].startswith(OAUTH2_AUTHORIZE)
    assert "channel=homeassistant" in result["url"]

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "rt",
            "access_token": "at",
            "token_type": "Bearer",
            "expires_in": 3600,
        },
    )
    return await hass.config_entries.flow.async_configure(result["flow_id"])


@pytest.mark.asyncio
async def test_full_oauth_flow(
    hass: HomeAssistant,
    hass_client_no_auth,
    aioclient_mock,
    current_request_with_host,
    setup_credentials,
):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    with (
        patch(
            "custom_components.navimow_simple.NavimowClient.async_get_devices",
            return_value=DEVICES,
        ),
        patch(
            "custom_components.navimow_simple.NavimowClient.async_get_status",
            return_value=STATUS,
        ),
        patch(
            "homeassistant.config_entries.ConfigEntries."
            "async_forward_entry_setups",
            return_value=None,
        ),
    ):
        result = await _drive_oauth_to_token(
            hass, hass_client_no_auth, aioclient_mock, result
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["token"]["access_token"] == "at"


@pytest.mark.asyncio
async def test_user_flow_registers_implementation_without_setup(
    hass: HomeAssistant,
    current_request_with_host,
):
    # OHNE async_setup_component: HA ruft async_setup für eine frische
    # OAuth-Integration nicht vor dem Flow auf. Der Flow muss die
    # Implementation selbst registrieren, sonst -> "missing_configuration".
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert "channel=homeassistant" in result["url"]


@pytest.mark.asyncio
async def test_user_flow_aborts_if_already_configured(
    hass: HomeAssistant,
    current_request_with_host,
    setup_credentials,
):
    _entry().add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.asyncio
async def test_reauth_shows_confirm_form(hass: HomeAssistant):
    entry = _entry()
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"


@pytest.mark.asyncio
async def test_reauth_success_updates_entry(
    hass: HomeAssistant,
    hass_client_no_auth,
    aioclient_mock,
    current_request_with_host,
    setup_credentials,
):
    entry = _entry()
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    # Submit the confirm form → proceeds into the OAuth external step.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {}
    )

    result = await _drive_oauth_to_token(
        hass, hass_client_no_auth, aioclient_mock, result
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["token"]["access_token"] == "at"
