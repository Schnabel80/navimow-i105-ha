from homeassistant.components.lawn_mower import LawnMowerActivity

from custom_components.navimow_simple import const


def test_core_constants_present():
    assert const.DOMAIN == "navimow_simple"
    assert const.BASE_URL.startswith("https://")
    assert const.UPDATE_INTERVAL_SECONDS == 90
    assert const.SUCCESS_CODE == 1


def test_state_map_real_values():
    assert const.STATE_MAP["isDocked"] == LawnMowerActivity.DOCKED
    assert const.STATE_MAP["isRunning"] == LawnMowerActivity.MOWING
    assert const.STATE_MAP["isDocking"] == LawnMowerActivity.RETURNING
    assert const.STATE_MAP["isPaused"] == LawnMowerActivity.PAUSED


def test_commands_cover_actions_with_google_grammar():
    for action in ("start", "pause", "dock", "resume", "stop"):
        assert action in const.COMMANDS
    assert const.COMMANDS["start"]["command"].startswith(
        "action.devices.commands."
    )
    assert const.COMMANDS["start"]["params"] == {"on": True}
