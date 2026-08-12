"""Generated from plugin_sofar.py @ 27875b3b by scripts/generate_sofar_model.py.

Do not hand-edit — re-run the generator instead. See scripts/generate_sofar_model.py
for the translation rules.
"""

from __future__ import annotations

from modbus_connection.model import Component, gauge, int32, integer, string


class BatteryPack(Component):
    """19 fields, generated — see module docstring."""

    max_span = 48

    bms_version = integer(36875, signed=False)  # 0x900B, allowedtypes=BAT_BTS
    realtime_capacity = integer(36878, signed=False)  # 0x900E, allowedtypes=BAT_BTS
    total_voltage = gauge(36879, 0.1, signed=False)  # 0x900F, allowedtypes=BAT_BTS
    total_current = gauge(36880, 0.1, signed=True)  # 0x9010, allowedtypes=BAT_BTS
    soc = integer(36882, signed=False)  # 0x9012, allowedtypes=BAT_BTS
    soh = integer(36883, signed=False)  # 0x9013, allowedtypes=BAT_BTS
    pack_id = integer(36932, signed=False)  # 0x9044, allowedtypes=BAT_BTS
    pack_time = int32(36933)  # 0x9045, allowedtypes=BAT_BTS
    pack_serial_number = string(36936, 9)  # 0x9048, allowedtypes=BAT_BTS
    cell_max_voltage = gauge(36969, 0.001, signed=False)  # 0x9069, allowedtypes=BAT_BTS
    cell_min_voltage = gauge(36970, 0.001, signed=False)  # 0x906A, allowedtypes=BAT_BTS
    pack_temperature_mos = gauge(36975, 0.1, signed=True)  # 0x906F, allowedtypes=BAT_BTS
    pack_temperature_env = gauge(36976, 0.1, signed=True)  # 0x9070, allowedtypes=BAT_BTS
    pack_current = gauge(36977, 0.1, signed=True)  # 0x9071, allowedtypes=BAT_BTS
    pack_remaining_capacity = gauge(36978, 0.1, signed=False)  # 0x9072, allowedtypes=BAT_BTS
    pack_full_charge_capacity = gauge(36979, 0.1, signed=False)  # 0x9073, allowedtypes=BAT_BTS
    pack_cycles = integer(36980, signed=False)  # 0x9074, allowedtypes=BAT_BTS
