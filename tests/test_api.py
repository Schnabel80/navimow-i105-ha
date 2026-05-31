import pytest
from aioresponses import aioresponses

from custom_components.navimow_simple import const
from custom_components.navimow_simple.api import (
    NavimowApiError,
    NavimowAuthError,
    NavimowClient,
)


class _FakeTokens:
    def __init__(self):
        self.calls: list[bool] = []
        self.token = "tok-1"

    async def async_get_valid_token(self, force_refresh: bool = False) -> str:
        self.calls.append(force_refresh)
        if force_refresh:
            self.token = "tok-2"
        return self.token


@pytest.fixture
def tokens():
    return _FakeTokens()


@pytest.mark.asyncio
async def test_get_devices_sends_bearer_and_requestid(tokens):
    import aiohttp

    with aioresponses() as m:
        m.get(
            f"{const.BASE_URL}{const.PATH_AUTH_LIST}",
            payload={"code": "0", "data": [{"deviceSn": "X"}]},
        )
        async with aiohttp.ClientSession() as session:
            client = NavimowClient(session, tokens)
            data = await client.async_get_devices()

    assert data == [{"deviceSn": "X"}]
    req = next(iter(m.requests.values()))[0]
    headers = req.kwargs["headers"]
    assert headers["Authorization"] == "Bearer tok-1"
    assert "requestId" in headers and len(headers["requestId"]) >= 10


@pytest.mark.asyncio
async def test_get_status_posts_sn(tokens):
    import aiohttp

    with aioresponses() as m:
        m.post(
            f"{const.BASE_URL}{const.PATH_STATUS}",
            payload={"code": "0", "data": {"vehicleState": "isDocked"}},
        )
        async with aiohttp.ClientSession() as session:
            client = NavimowClient(session, tokens)
            data = await client.async_get_status("SN1")

    assert data["vehicleState"] == "isDocked"
    req = next(iter(m.requests.values()))[0]
    assert req.kwargs["json"] == {const.DEVICE_SN_KEY: "SN1"}


@pytest.mark.asyncio
async def test_send_command_merges_action_payload(tokens):
    import aiohttp

    with aioresponses() as m:
        m.post(
            f"{const.BASE_URL}{const.PATH_COMMANDS}", payload={"code": "0"}
        )
        async with aiohttp.ClientSession() as session:
            client = NavimowClient(session, tokens)
            await client.async_send_command("SN1", "start")

    req = next(iter(m.requests.values()))[0]
    body = req.kwargs["json"]
    assert body[const.DEVICE_SN_KEY] == "SN1"
    for k, v in const.COMMANDS["start"].items():
        assert body[k] == v
