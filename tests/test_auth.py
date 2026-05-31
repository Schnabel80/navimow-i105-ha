import time

import pytest

from custom_components.navimow_simple.auth import TokenManager


@pytest.mark.asyncio
async def test_returns_cached_token_without_relogin():
    calls = []

    async def login():
        calls.append(1)
        return {"access_token": "A", "expires_at": time.time() + 3600}

    tm = TokenManager(login=login)
    assert await tm.async_get_valid_token() == "A"
    assert await tm.async_get_valid_token() == "A"
    assert len(calls) == 1  # nur ein Login


@pytest.mark.asyncio
async def test_force_refresh_relogins():
    seq = iter(["A", "B"])

    async def login():
        return {"access_token": next(seq), "expires_at": time.time() + 3600}

    tm = TokenManager(login=login)
    assert await tm.async_get_valid_token() == "A"
    assert await tm.async_get_valid_token(force_refresh=True) == "B"


@pytest.mark.asyncio
async def test_expired_token_triggers_relogin():
    seq = iter(
        [
            {"access_token": "A", "expires_at": time.time() - 1},
            {"access_token": "B", "expires_at": time.time() + 3600},
        ]
    )

    async def login():
        return next(seq)

    tm = TokenManager(login=login)
    assert await tm.async_get_valid_token() == "A"  # erster Login
    assert await tm.async_get_valid_token() == "B"  # abgelaufen -> relogin
