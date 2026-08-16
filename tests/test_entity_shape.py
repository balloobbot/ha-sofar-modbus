"""Structural invariants for every entity this integration creates.

These are pure metadata checks (no coordinator/hass fixture needed) encoding
the two bug classes that have actually bitten this project before: an enum
sensor/select whose declared options fall out of sync with the library enum
it's read from (CHANGELOG's 0.3.1 entry), and a hardcoded/missing translation
(0.3.13, 0.4.0). Keeping these true is now enforced here instead of by a
generator script or by hand.
"""

from __future__ import annotations

import json
from enum import IntEnum
from pathlib import Path
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.helpers.entity import Entity
from sofar_modbus.modern import (
    BatConfigCellType,
    BatConfigProtocol,
    ChargerUseMode,
    EpsControlMode,
    FeedinLimitationMode,
    ParallelMasterslave,
    PassiveModeTimeoutAction,
    RemoteSwitchOnOff,
    SyncRtcResult,
    SystemState,
)

from custom_components.sofar_modbus import button, number, select, switch
from custom_components.sofar_modbus.sensor import SENSOR_DESCRIPTIONS, _enum_label

_STRINGS_PATH = Path(__file__).parent.parent / "custom_components" / "sofar_modbus" / "strings.json"
_TRANSLATIONS_PATH = Path(__file__).parent.parent / "custom_components" / "sofar_modbus" / "translations" / "en.json"

# Every SENSOR_DESCRIPTIONS row with device_class=ENUM, matched to the IntEnum
# its native_value is actually drawn from (nothing on the description names
# this, so it's hand-mapped here and cross-checked for completeness below).
_ENUM_SENSOR_KEYS = {
    "system_state": SystemState,
    "parallel_masterslave": ParallelMasterslave,
    "bat_config_protocol": BatConfigProtocol,
    "bat_config_cell_type": BatConfigCellType,
    "sync_rtc_result": SyncRtcResult,
}

# select.py's hand-maintained enum -> HA option slug dicts, each paired with
# its entity class and the library enum it must stay in sync with.
_SELECT_SPECS: list[tuple[type[SelectEntity], dict[Any, str], type[IntEnum]]] = [
    (select.RemoteSwitchSelect, select._REMOTE_SWITCH_OPTIONS, RemoteSwitchOnOff),
    (select.FeedInLimitationModeSelect, select._FEEDIN_LIMITATION_OPTIONS, FeedinLimitationMode),
    (select.ChargerUseModeSelect, select._CHARGER_USE_MODE_OPTIONS, ChargerUseMode),
    (select.EpsModeSelect, select._EPS_MODE_OPTIONS, EpsControlMode),
    (select.PassiveTimeoutActionSelect, select._PASSIVE_TIMEOUT_ACTION_OPTIONS, PassiveModeTimeoutAction),
]

_OTHER_WRITE_ENTITY_CLASSES: list[tuple[str, type[Entity]]] = [
    ("switch", switch.ActivePowerControlSwitch),
    ("number", number.FeedInMaxPowerNumber),
    ("number", number.ActivePowerExportLimitNumber),
    ("number", number.PassiveTimeoutNumber),
    ("number", number.PassiveGridPowerNumber),
    ("number", number.PassiveBatteryPowerMinNumber),
    ("number", number.PassiveBatteryPowerMaxNumber),
    ("button", button.FeedInUpdateButton),
    ("button", button.ActivePowerControlUpdateButton),
    ("button", button.PassiveTimeoutUpdateButton),
    ("button", button.PassivePowerUpdateButton),
    ("button", button.RtcSyncButton),
]


def _translation_key(cls: type[Entity]) -> str:
    """`_attr_translation_key` is wired through HA's cached-property
    machinery, so a class-level read returns the descriptor, not the value
    — a bare (no __init__) instance is enough to resolve it properly.
    """
    key = cls.__new__(cls).translation_key
    assert key is not None
    return key


def test_enum_sensor_coverage() -> None:
    """Every device_class=ENUM sensor must be accounted for in _ENUM_SENSOR_KEYS.

    Catches a new ENUM sensor being added without extending this test, rather
    than the test silently not covering it.
    """
    enum_keys = {d.key for d in SENSOR_DESCRIPTIONS if d.device_class == SensorDeviceClass.ENUM}
    assert enum_keys == set(_ENUM_SENSOR_KEYS)


def test_enum_sensor_options_match_underlying_enum() -> None:
    by_key = {d.key: d for d in SENSOR_DESCRIPTIONS}
    for key, enum_cls in _ENUM_SENSOR_KEYS.items():
        expected = {_enum_label(member.name) for member in enum_cls}
        assert set(by_key[key].options or []) == expected, key


def test_select_option_maps_cover_full_enum() -> None:
    for cls, mapping, enum_cls in _SELECT_SPECS:
        assert set(mapping) == set(enum_cls), cls.__name__


def test_select_state_strings_cover_every_option() -> None:
    strings = json.loads(_STRINGS_PATH.read_text())
    for cls, mapping, _enum_cls in _SELECT_SPECS:
        key = _translation_key(cls)
        states = strings["entity"]["select"][key]["state"]
        assert set(states) == set(mapping.values()), key


def test_translation_keys_have_name_entries() -> None:
    entity_strings = json.loads(_STRINGS_PATH.read_text())["entity"]

    for description in SENSOR_DESCRIPTIONS:
        assert description.translation_key in entity_strings["sensor"], description.translation_key

    for cls, _mapping, _enum_cls in _SELECT_SPECS:
        assert _translation_key(cls) in entity_strings["select"], cls.__name__

    for platform, entity_cls in _OTHER_WRITE_ENTITY_CLASSES:
        assert _translation_key(entity_cls) in entity_strings[platform], entity_cls.__name__


def test_strings_and_translations_stay_identical() -> None:
    assert _STRINGS_PATH.read_text() == _TRANSLATIONS_PATH.read_text()
