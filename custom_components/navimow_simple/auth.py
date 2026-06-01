"""OAuth2-Implementation + Token-Adapter für Navimow Simple."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from homeassistant.helpers.config_entry_oauth2_flow import (
    LocalOAuth2Implementation,
    OAuth2Session,
)

from .const import (
    CLIENT_ID,
    CLIENT_SECRET,
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


class NavimowOAuth2Implementation(LocalOAuth2Implementation):
    """LocalOAuth2Implementation mit channel=homeassistant in der URL."""

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(
            hass,
            DOMAIN,
            CLIENT_ID,
            CLIENT_SECRET,
            OAUTH2_AUTHORIZE,
            OAUTH2_TOKEN,
        )

    @property
    def name(self) -> str:
        return "Navimow"

    async def async_generate_authorize_url(
        self, *args: Any, **kwargs: Any
    ) -> str:
        url = await super().async_generate_authorize_url(*args, **kwargs)
        parsed = urlparse(url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query.setdefault("channel", "homeassistant")
        return urlunparse(parsed._replace(query=urlencode(query)))


class OAuth2TokenSource:
    """Adapter: OAuth2Session -> TokenSource (für NavimowClient)."""

    def __init__(self, session: OAuth2Session) -> None:
        self._session = session

    async def async_get_valid_token(self, force_refresh: bool = False) -> str:
        await self._session.async_ensure_token_valid()
        return self._session.token["access_token"]
