"""Generated from plugin_sofar.py @ 27875b3b by scripts/generate_sofar_model.py.

Do not hand-edit — re-run the generator instead. See scripts/generate_sofar_model.py
for the translation rules.
"""

from __future__ import annotations

from modbus_connection.model import Component, NumberField, gauge, int32, integer


class SettingsReadback(Component):
    """37 fields, generated — see module docstring."""

    feedin_limitation_mode = integer(4131, signed=False)  # 0x1023, allowedtypes=HYBRID | PV
    feedin_max_power = gauge(4132, 100, signed=False)  # 0x1024, allowedtypes=HYBRID | PV, internal
    eps_control = integer(4137, signed=False)  # 0x1029, allowedtypes=HYBRID | EPS
    passive_eps_wait_time = integer(4138, signed=False)  # 0x102A, allowedtypes=HYBRID | EPS
    parallel_masterslave = integer(4150, signed=False)  # 0x1036, allowedtypes=HYBRID | PV | X3 | PM
    parallel_address = integer(4151, signed=False)  # 0x1037, allowedtypes=HYBRID | PV | X3 | PM, internal
    bat_config_id = integer(4164, signed=False)  # 0x1044, allowedtypes=HYBRID
    bat_config_address_1 = integer(4165, signed=False)  # 0x1045, allowedtypes=HYBRID
    bat_config_protocol = integer(4166, signed=False)  # 0x1046, allowedtypes=HYBRID
    bat_config_overvoltage_protection = gauge(4167, 0.1, signed=False)  # 0x1047, allowedtypes=HYBRID
    bat_config_charging_voltage = gauge(4168, 0.1, signed=False)  # 0x1048, allowedtypes=HYBRID
    bat_config_undervoltage_protection = gauge(4169, 0.1, signed=False)  # 0x1049, allowedtypes=HYBRID
    bat_config_minimum_discharge_voltage = gauge(4170, 0.1, signed=False)  # 0x104A, allowedtypes=HYBRID
    bat_config_maximum_charge_current_limit = gauge(4171, 0.01, signed=False)  # 0x104B, allowedtypes=HYBRID
    bat_config_maximum_discharge_current_limit = gauge(4172, 0.01, signed=False)  # 0x104C, allowedtypes=HYBRID
    bat_config_depth_of_discharge = integer(4173, signed=False)  # 0x104D, allowedtypes=HYBRID
    bat_config_end_of_discharge = integer(4174, signed=False)  # 0x104E, allowedtypes=HYBRID
    bat_config_capacity = integer(4175, signed=False)  # 0x104F, allowedtypes=HYBRID
    bat_config_rated_battery_voltage = gauge(4176, 0.1, signed=False)  # 0x1050, allowedtypes=HYBRID
    bat_config_cell_type = integer(4177, signed=False)  # 0x1051, allowedtypes=HYBRID
    bat_config_eps_buffer = integer(4178, signed=False)  # 0x1052, allowedtypes=HYBRID
    bat_config_address_2 = integer(4180, signed=False)  # 0x1054, allowedtypes=HYBRID
    bat_config_address_3 = integer(4181, signed=False)  # 0x1055, allowedtypes=HYBRID
    bat_config_address_4 = integer(4182, signed=False)  # 0x1056, allowedtypes=HYBRID
    bat_config_tempco = gauge(4183, 0.1, signed=True)  # 0x1057, allowedtypes=HYBRID
    bat_config_voltage_float = gauge(4186, 0.1, signed=False)  # 0x105A, allowedtypes=HYBRID
    remote_switch_on_off = integer(4356, signed=False)  # 0x1104, allowedtypes=HYBRID | PV, internal
    charger_use_mode = integer(4368, signed=False)  # 0x1110, allowedtypes=HYBRID, internal
    sync_rtc_result = integer(4106, signed=False)  # 0x100A, allowedtypes=HYBRID
    passive_mode_timeout = integer(4484, signed=False)  # 0x1184, allowedtypes=HYBRID
    passive_mode_timeout_action = integer(4485, signed=False)  # 0x1185, allowedtypes=HYBRID, internal
    passive_mode_grid_power = int32(4487)  # 0x1187, allowedtypes=HYBRID, internal
    passive_mode_battery_power_min = int32(4489)  # 0x1189, allowedtypes=HYBRID, internal
    passive_mode_battery_power_max = int32(4491)  # 0x118B, allowedtypes=HYBRID, internal

    # value_function_disabled_enabled: 0/1 -> Disabled/Enabled
    battery_active_control = NumberField(4139, signed=False, convert={0: "Disabled", 1: "Enabled"})
    parallel_control = NumberField(4149, signed=False, convert={0: "Disabled", 1: "Enabled"})
