import aiohttp
import pytest
from aioresponses import aioresponses

from custom_components.navimow_simple import const
from custom_components.navimow_simple.api import (
    NavimowApiError,
    NavimowAuthError,
    NavimowClient,
    NavimowRateLimitError,
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
async def test_get_devices_parses_envelope_and_headers(tokens):
    with aioresponses() as m:
        m.get(
            f"{const.BASE_URL}{const.PATH_AUTH_LIST}",
            payload={
                "code": 1,
                "data": {
                    "payload": {"devices": [{"id": "X", "model": "i105"}]}
                },
            },
        )
        async with aiohttp.ClientSession() as session:
            client = NavimowClient(session, tokens)
            devices = await client.async_get_devices()

    assert devices == [{"id": "X", "model": "i105"}]
    req = next(iter(m.requests.values()))[0]
    headers = req.kwargs["headers"]
    assert headers["Authorization"] == "Bearer tok-1"
    assert len(headers["requestId"]) >= 10


@pytest.mark.asyncio
async def test_get_status_posts_device_object_and_unwraps(tokens):
    with aioresponses() as m:
        m.post(
            f"{const.BASE_URL}{const.PATH_STATUS}",
            payload={
                "code": 1,
                "data": {
                    "payload": {
                        "devices": [
                            {
                                "id": "SN1",
                                "vehicleState": "isDocked",
                                "capacityRemaining": [
                                    {"unit": "PERCENTAGE", "rawValue": 88}
                                ],
                            }
                        ]
                    }
                },
            },
        )
        async with aiohttp.ClientSession() as session:
            client = NavimowClient(session, tokens)
            status = await client.async_get_status("SN1")

    assert status["vehicleState"] == "isDocked"
    req = next(iter(m.requests.values()))[0]
    assert req.kwargs["json"] == {"devices": [{"id": "SN1"}]}


@pytest.mark.asyncio
async def test_send_command_builds_google_grammar_body(tokens):
    with aioresponses() as m:
        m.post(
            f"{const.BASE_URL}{const.PATH_COMMANDS}",
            payload={"code": 1, "data": {"payload": {"commands": []}}},
        )
        async with aiohttp.ClientSession() as session:
            client = NavimowClient(session, tokens)
            await client.async_send_command("SN1", "start")

    req = next(iter(m.requests.values()))[0]
    body = req.kwargs["json"]
    cmd = body["commands"][0]
    assert cmd["devices"] == [{"id": "SN1"}]
    assert cmd["execution"]["command"] == ("action.devices.commands.StartStop")
    assert cmd["execution"]["params"] == {"on": True}


@pytest.mark.asyncio
async def test_send_command_already_in_state_is_success(tokens):
    with aioresponses() as m:
        m.post(
            f"{const.BASE_URL}{const.PATH_COMMANDS}",
            payload={
                "code": 1,
                "data": {
                    "payload": {
                        "commands": [
                            {"status": "ERROR", "errorCode": "alreadyInState"}
                        ]
                    }
                },
            },
        )
        async with aiohttp.ClientSession() as session:
            client = NavimowClient(session, tokens)
            await client.async_send_command("SN1", "dock")  # darf NICHT werfen


@pytest.mark.asyncio
async def test_send_command_real_error_raises(tokens):
    with aioresponses() as m:
        m.post(
            f"{const.BASE_URL}{const.PATH_COMMANDS}",
            payload={
                "code": 1,
                "data": {
                    "payload": {
                        "commands": [
                            {"status": "ERROR", "errorCode": "deviceOffline"}
                        ]
                    }
                },
            },
        )
        async with aiohttp.ClientSession() as session:
            client = NavimowClient(session, tokens)
            with pytest.raises(NavimowApiError):
                await client.async_send_command("SN1", "start")


@pytest.mark.asyncio
async def test_4003_triggers_one_retry_with_force_refresh(tokens):
    with aioresponses() as m:
        m.post(f"{const.BASE_URL}{const.PATH_STATUS}", payload={"code": 4003})
        m.post(
            f"{const.BASE_URL}{const.PATH_STATUS}",
            payload={
                "code": 1,
                "data": {
                    "payload": {"devices": [{"vehicleState": "isDocked"}]}
                },
            },
        )
        async with aiohttp.ClientSession() as session:
            client = NavimowClient(session, tokens)
            status = await client.async_get_status("SN1")

    assert status["vehicleState"] == "isDocked"
    assert tokens.calls == [False, True]


@pytest.mark.asyncio
async def test_persistent_4003_raises_auth_error(tokens):
    with aioresponses() as m:
        m.post(f"{const.BASE_URL}{const.PATH_STATUS}", payload={"code": 4003})
        m.post(f"{const.BASE_URL}{const.PATH_STATUS}", payload={"code": 4003})
        async with aiohttp.ClientSession() as session:
            client = NavimowClient(session, tokens)
            with pytest.raises(NavimowAuthError):
                await client.async_get_status("SN1")


@pytest.mark.asyncio
async def test_api_error_on_non_success_code(tokens):
    with aioresponses() as m:
        m.post(
            f"{const.BASE_URL}{const.PATH_STATUS}",
            payload={"code": 10003, "desc": "ErrorCode_10003"},
        )
        async with aiohttp.ClientSession() as session:
            client = NavimowClient(session, tokens)
            with pytest.raises(NavimowApiError):
                await client.async_get_status("SN1")


def test_rate_limit_error_is_api_error():
    # Muss von NavimowApiError erben → `except NavimowError` greift weiterhin.
    assert issubclass(NavimowRateLimitError, NavimowApiError)


@pytest.mark.asyncio
async def test_circuit_breaker_raises_rate_limit_error(tokens):
    # 4001 = Gateway-Circuit-Breaker → eigener transienter Fehlertyp.
    with aioresponses() as m:
        m.post(
            f"{const.BASE_URL}{const.PATH_STATUS}",
            payload={"code": 4001, "desc": "url Circuit Breaker"},
        )
        async with aiohttp.ClientSession() as session:
            client = NavimowClient(session, tokens)
            with pytest.raises(NavimowRateLimitError):
                await client.async_get_status("SN1")


@pytest.mark.asyncio
async def test_client_error_wrapped_as_api_error(tokens):
    with aioresponses() as m:
        m.get(
            f"{const.BASE_URL}{const.PATH_AUTH_LIST}",
            exception=aiohttp.ClientError("connection reset"),
        )
        async with aiohttp.ClientSession() as session:
            client = NavimowClient(session, tokens)
            with pytest.raises(NavimowApiError):
                await client.async_get_devices()


@pytest.mark.asyncio
async def test_get_status_empty_devices_raises(tokens):
    with aioresponses() as m:
        m.post(
            f"{const.BASE_URL}{const.PATH_STATUS}",
            payload={"code": 1, "data": {"payload": {"devices": []}}},
        )
        async with aiohttp.ClientSession() as session:
            client = NavimowClient(session, tokens)
            with pytest.raises(NavimowApiError):
                await client.async_get_status("SN1")
