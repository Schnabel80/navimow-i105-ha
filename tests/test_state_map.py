from homeassistant.components.lawn_mower import LawnMowerActivity

from custom_components.navimow_simple.api import state_to_activity


def test_known_docked():
    assert state_to_activity("isDocked") == LawnMowerActivity.DOCKED


def test_unknown_defaults_to_error():
    assert state_to_activity("voelliger_quatsch") == LawnMowerActivity.ERROR


def test_none_defaults_to_error():
    assert state_to_activity(None) == LawnMowerActivity.ERROR
