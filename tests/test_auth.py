import pytest

from custom_components.navimow_simple.auth import (
    NavimowOAuth2Implementation,
    OAuth2TokenSource,
)


@pytest.mark.asyncio
async def test_implementation_constructs_with_name(hass):
    impl = NavimowOAuth2Implementation(hass)
    assert impl.name == "Navimow"


@pytest.mark.asyncio
async def test_authorize_url_has_channel(hass):
    # "my" lets async_get_redirect_uri return a static URL without a
    # live HTTP request context.
    hass.config.components.add("my")
    impl = NavimowOAuth2Implementation(hass)
    url = await impl.async_generate_authorize_url("flow123")
    assert "channel=homeassistant" in url


class _FakeSession:
    def __init__(self):
        self.ensured = False
        self.token = {"access_token": "abc"}

    async def async_ensure_token_valid(self):
        self.ensured = True


@pytest.mark.asyncio
async def test_token_source_returns_access_token():
    s = _FakeSession()
    src = OAuth2TokenSource(s)
    assert await src.async_get_valid_token() == "abc"
    assert s.ensured is True
