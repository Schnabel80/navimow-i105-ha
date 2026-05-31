from custom_components.navimow_simple import const


def test_core_constants_present():
    assert const.DOMAIN == "navimow_simple"
    assert const.BASE_URL.startswith("https://")
    assert const.UPDATE_INTERVAL_SECONDS == 90


def test_state_map_has_known_docked_value():
    from homeassistant.components.lawn_mower import LawnMowerActivity

    assert const.STATE_MAP["isDocked"] == LawnMowerActivity.DOCKED


def test_commands_cover_required_actions():
    for action in ("start", "pause", "dock"):
        assert action in const.COMMANDS
