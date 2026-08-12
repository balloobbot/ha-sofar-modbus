"""Generated from plugin_sofar.py @ 27875b3b. Bitmasks and per-field allowedtypes.

Do not hand-edit — re-run scripts/generate_sofar_model.py.
"""

from __future__ import annotations

# -- inverter-type bitmasks (ported verbatim from plugin_sofar.py) --------
GEN = 0x1
GEN2 = 0x2
GEN3 = 0x4
GEN4 = 0x8
X1 = 0x100
X3 = 0x200
PV = 0x400
AC = 0x800
HYBRID = 0x1000
MIC = 0x2000
EPS = 0x8000
DCB = 0x10000
PM = 0x20000
MPPT3 = 0x40000
MPPT4 = 0x80000
MPPT6 = 0x100000
MPPT8 = 0x200000
MPPT10 = 0x400000
BAT_BTS = 0x1000000
ALLDEFAULT = 0
ALL_GEN_GROUP = 0xF
ALL_X_GROUP = 0x300
ALL_TYPE_GROUP = 0x3C00
ALL_EPS_GROUP = 0x8000
ALL_DCB_GROUP = 0x10000
ALL_PM_GROUP = 0x20000
ALL_MPPT_GROUP = 0x7C0000

# -- per-field allowedtypes, by component -----------------------------------
REALTIME_ALLOWEDTYPES: dict[str, int] = {
    'system_state': 0x1400,
    'fault_1': 0x1400,
    'fault_2': 0x1400,
    'fault_3': 0x1400,
    'fault_4': 0x1400,
    'fault_5': 0x1400,
    'fault_6': 0x1400,
    'fault_7': 0x1400,
    'fault_8': 0x1400,
    'fault_9': 0x1400,
    'fault_10': 0x1400,
    'fault_11': 0x1400,
    'fault_12': 0x1400,
    'waiting_time': 0x1400,
    'inverter_temperature_1': 0x1400,
    'inverter_temperature_2': 0x1400,
    'heatsink_temperature_1': 0x1400,
    'heatsink_temperature_2': 0x1400,
    'module_temperature_1': 0x1400,
    'module_temperature_2': 0x1400,
    'rtc': 0x1400,
    'serial_number': 0x1400,
    'hardware_version': 0x1400,
    'software_version': 0x1400,
    'grid_frequency': 0x1400,
    'active_power_output_total': 0x1400,
    'reactive_power_output_total': 0x1400,
    'apparent_power_output_total': 0x1400,
    'active_power_pcc_total': 0x1400,
    'reactive_power_pcc_total': 0x1400,
    'apparent_power_pcc_total': 0x1400,
    'voltage_l1': 0x1400,
    'current_output_l1': 0x1400,
    'active_power_output_l1': 0x1400,
    'reactive_power_output_l1': 0x1400,
    'power_factor_output_l1': 0x1400,
    'current_pcc_l1': 0x1400,
    'active_power_pcc_l1': 0x1400,
    'reactive_power_pcc_l1': 0x1400,
    'power_factor_pcc_l1': 0x1400,
    'voltage_l2': 0x1400,
    'current_output_l2': 0x1400,
    'active_power_output_l2': 0x1400,
    'reactive_power_output_l2': 0x1400,
    'power_factor_output_l2': 0x1400,
    'current_pcc_l2': 0x1400,
    'active_power_pcc_l2': 0x1400,
    'reactive_power_pcc_l2': 0x1400,
    'power_factor_pcc_l2': 0x1400,
    'voltage_l3': 0x1400,
    'current_output_l3': 0x1400,
    'active_power_output_l3': 0x1400,
    'reactive_power_output_l3': 0x1400,
    'power_factor_output_l3': 0x1400,
    'current_pcc_l3': 0x1400,
    'active_power_pcc_l3': 0x1400,
    'reactive_power_pcc_l3': 0x1400,
    'power_factor_pcc_l3': 0x1400,
    'active_power_pv_ext': 0x1400,
    'active_power_load_sys': 0x1400,
    'voltage_phase_l1n': 0x1400,
    'current_output_l1n': 0x1400,
    'active_power_output_l1n': 0x1400,
    'current_pcc_l1n': 0x1400,
    'active_power_pcc_l1n': 0x1400,
    'voltage_phase_l2n': 0x1400,
    'current_output_l2n': 0x1400,
    'active_power_output_l2n': 0x1400,
    'current_pcc_l2n': 0x1400,
    'active_power_pcc_l2n': 0x1400,
    'voltage_line_l1': 0x1400,
    'voltage_line_l2': 0x1400,
    'voltage_line_l3': 0x1400,
    'active_power_offgrid_total': 0x9000,
    'reactive_power_offgrid_total': 0x9000,
    'apparent_power_offgrid_total': 0x9000,
    'offgrid_frequency': 0x9000,
    'offgrid_voltage': 0x9100,
    'offgrid_voltage_l1': 0x9200,
    'offgrid_current_output': 0x9100,
    'offgrid_current_output_l1': 0x9200,
    'offgrid_active_power_output': 0x9100,
    'offgrid_active_power_output_l1': 0x9200,
    'offgrid_reactive_power_output': 0x9100,
    'offgrid_reactive_power_output_l1': 0x9200,
    'offgrid_apparent_power_output': 0x9100,
    'offgrid_apparent_power_output_l1': 0x9200,
    'offgrid_loadpeakratio': 0x9100,
    'offgrid_loadpeakratio_l1': 0x9200,
    'offgrid_voltage_l2': 0x9200,
    'offgrid_current_output_l2': 0x9200,
    'offgrid_active_power_output_l2': 0x9200,
    'offgrid_reactive_power_output_l2': 0x9200,
    'offgrid_apparent_power_output_l2': 0x9200,
    'offgrid_loadpeakratio_l2': 0x9200,
    'offgrid_voltage_l3': 0x9200,
    'offgrid_current_output_l3': 0x9200,
    'offgrid_active_power_output_l3': 0x9200,
    'offgrid_reactive_power_output_l3': 0x9200,
    'offgrid_apparent_power_output_l3': 0x9200,
    'offgrid_loadpeakratio_l3': 0x9200,
    'offgrid_voltage_output_l1n': 0x9200,
    'offgrid_current_output_l1n': 0x9200,
    'offgrid_active_power_output_l1n': 0x9200,
    'offgrid_voltage_output_l2n': 0x9200,
    'offgrid_current_output_l2n': 0x9200,
    'offgrid_active_power_output_l2n': 0x9200,
    'pv_voltage_1': 0x1401,
    'pv_current_1': 0x1401,
    'pv_power_1': 0x1401,
    'pv_voltage_2': 0x1401,
    'pv_current_2': 0x1401,
    'pv_power_2': 0x1401,
    'pv_voltage_3': 0x7C1401,
    'pv_current_3': 0x7C1401,
    'pv_power_3': 0x7C1401,
    'pv_voltage_4': 0x781401,
    'pv_current_4': 0x781401,
    'pv_power_4': 0x781401,
    'pv_voltage_5': 0x701401,
    'pv_current_5': 0x701401,
    'pv_power_5': 0x701401,
    'pv_voltage_6': 0x701401,
    'pv_current_6': 0x701401,
    'pv_power_6': 0x701401,
    'pv_voltage_7': 0x601401,
    'pv_current_7': 0x601401,
    'pv_power_7': 0x601401,
    'pv_voltage_8': 0x601401,
    'pv_current_8': 0x601401,
    'pv_power_8': 0x601401,
    'pv_voltage_9': 0x401401,
    'pv_current_9': 0x401401,
    'pv_power_9': 0x401401,
    'pv_voltage_10': 0x401401,
    'pv_current_10': 0x401401,
    'pv_power_10': 0x401401,
    'pv_power_total': 0x1401,
    'battery_voltage_1': 0x1000,
    'battery_current_1': 0x1000,
    'battery_power_1': 0x1000,
    'battery_temperature_1': 0x1000,
    'battery_capacity_1': 0x1000,
    'battery_state_of_health_1': 0x1000,
    'battery_charge_cycle_1': 0x1000,
    'battery_voltage_2': 0x1000,
    'battery_current_2': 0x1000,
    'battery_power_2': 0x1000,
    'battery_temperature_2': 0x1000,
    'battery_capacity_2': 0x1000,
    'battery_state_of_health_2': 0x1000,
    'battery_charge_cycle_2': 0x1000,
    'battery_voltage_3': 0x1001,
    'battery_current_3': 0x1001,
    'battery_power_3': 0x1001,
    'battery_temperature_3': 0x1001,
    'battery_capacity_3': 0x1001,
    'battery_state_of_health_3': 0x1001,
    'battery_charge_cycle_3': 0x1001,
    'battery_voltage_4': 0x1001,
    'battery_current_4': 0x1001,
    'battery_power_4': 0x1001,
    'battery_temperature_4': 0x1001,
    'battery_capacity_4': 0x1001,
    'battery_state_of_health_4': 0x1001,
    'battery_charge_cycle_4': 0x1001,
    'battery_voltage_5': 0x1001,
    'battery_current_5': 0x1001,
    'battery_power_5': 0x1001,
    'battery_temperature_5': 0x1001,
    'battery_capacity_5': 0x1001,
    'battery_state_of_health_5': 0x1001,
    'battery_charge_cycle_5': 0x1001,
    'battery_voltage_6': 0x1001,
    'battery_current_6': 0x1001,
    'battery_power_6': 0x1001,
    'battery_temperature_6': 0x1001,
    'battery_capacity_6': 0x1001,
    'battery_state_of_health_6': 0x1001,
    'battery_charge_cycle_6': 0x1001,
    'battery_voltage_7': 0x1001,
    'battery_current_7': 0x1001,
    'battery_power_7': 0x1001,
    'battery_temperature_7': 0x1001,
    'battery_capacity_7': 0x1001,
    'battery_state_of_health_7': 0x1001,
    'battery_charge_cycle_7': 0x1001,
    'battery_voltage_8': 0x1001,
    'battery_current_8': 0x1001,
    'battery_power_8': 0x1001,
    'battery_temperature_8': 0x1001,
    'battery_capacity_8': 0x1001,
    'battery_state_of_health_8': 0x1001,
    'battery_charge_cycle_8': 0x1001,
    'battery_power_total': 0x1000,
    'battery_capacity_total': 0x1000,
    'battery_state_of_health_total': 0x1000,
    'solar_generation_today': 0x1400,
    'solar_generation_total': 0x1400,
    'load_consumption_today': 0x1400,
    'load_consumption_total': 0x1400,
    'import_energy_today': 0x1400,
    'import_energy_total': 0x1400,
    'export_energy_today': 0x1400,
    'export_energy_total': 0x1400,
    'battery_input_energy_today': 0x1000,
    'battery_input_energy_total': 0x1000,
    'battery_output_energy_today': 0x1000,
    'battery_output_energy_total': 0x1000,
}

SETTINGS_ALLOWEDTYPES: dict[str, int] = {
    'feedin_limitation_mode': 0x1400,
    'feedin_max_power': 0x1400,
    'eps_control': 0x9000,
    'passive_eps_wait_time': 0x9000,
    'battery_active_control': 0x1000,
    'parallel_control': 0x21600,
    'parallel_masterslave': 0x21600,
    'parallel_address': 0x21600,
    'bat_config_id': 0x1000,
    'bat_config_address_1': 0x1000,
    'bat_config_protocol': 0x1000,
    'bat_config_overvoltage_protection': 0x1000,
    'bat_config_charging_voltage': 0x1000,
    'bat_config_undervoltage_protection': 0x1000,
    'bat_config_minimum_discharge_voltage': 0x1000,
    'bat_config_maximum_charge_current_limit': 0x1000,
    'bat_config_maximum_discharge_current_limit': 0x1000,
    'bat_config_depth_of_discharge': 0x1000,
    'bat_config_end_of_discharge': 0x1000,
    'bat_config_capacity': 0x1000,
    'bat_config_rated_battery_voltage': 0x1000,
    'bat_config_cell_type': 0x1000,
    'bat_config_eps_buffer': 0x1000,
    'bat_config_address_2': 0x1000,
    'bat_config_address_3': 0x1000,
    'bat_config_address_4': 0x1000,
    'bat_config_tempco': 0x1000,
    'bat_config_voltage_float': 0x1000,
    'remote_switch_on_off': 0x1400,
    'charger_use_mode': 0x1000,
    'sync_rtc_result': 0x1000,
    'passive_mode_timeout': 0x1000,
    'passive_mode_timeout_action': 0x1000,
    'passive_mode_grid_power': 0x1000,
    'passive_mode_battery_power_min': 0x1000,
    'passive_mode_battery_power_max': 0x1000,
}

BATTERY_PACK_ALLOWEDTYPES: dict[str, int] = {
    'bms_version': 0x1000000,
    'realtime_capacity': 0x1000000,
    'total_voltage': 0x1000000,
    'total_current': 0x1000000,
    'soc': 0x1000000,
    'soh': 0x1000000,
    'pack_id': 0x1000000,
    'pack_time': 0x1000000,
    'pack_serial_number': 0x1000000,
    'cell_max_voltage': 0x1000000,
    'cell_min_voltage': 0x1000000,
    'pack_temperature_mos': 0x1000000,
    'pack_temperature_env': 0x1000000,
    'pack_current': 0x1000000,
    'pack_remaining_capacity': 0x1000000,
    'pack_full_charge_capacity': 0x1000000,
    'pack_cycles': 0x1000000,
}


def matches_inverter(inverterspec: int, entitymask: int) -> bool:
    """Port of sofar_plugin.matchInverterWithMask (no blacklist — that's HA-side)."""
    genmatch = ((inverterspec & entitymask & ALL_GEN_GROUP) != 0) or (entitymask & ALL_GEN_GROUP == 0)
    xmatch = ((inverterspec & entitymask & ALL_X_GROUP) != 0) or (entitymask & ALL_X_GROUP == 0)
    hybmatch = ((inverterspec & entitymask & ALL_TYPE_GROUP) != 0) or (entitymask & ALL_TYPE_GROUP == 0)
    epsmatch = ((inverterspec & entitymask & ALL_EPS_GROUP) != 0) or (entitymask & ALL_EPS_GROUP == 0)
    dcbmatch = ((inverterspec & entitymask & ALL_DCB_GROUP) != 0) or (entitymask & ALL_DCB_GROUP == 0)
    pmmatch = ((inverterspec & entitymask & ALL_PM_GROUP) != 0) or (entitymask & ALL_PM_GROUP == 0)
    mpptmatch = ((inverterspec & entitymask & ALL_MPPT_GROUP) != 0) or (entitymask & ALL_MPPT_GROUP == 0)
    return genmatch and xmatch and hybmatch and epsmatch and dcbmatch and pmmatch and mpptmatch


def served_fields(allowedtypes: dict[str, int], inverterspec: int) -> list[str]:
    """Names of fields this inverter type serves, in declared order."""
    return [key for key, mask in allowedtypes.items() if matches_inverter(inverterspec, mask)]


# Hand-written @property fields (see HANDWRITTEN_FIELDS in the generator) are
# not real Component fields, so Component.restrict_fields() doesn't know them
# — they're computed from underlying private fields that must be restricted
# in their place. Expand before calling restrict_fields(); keep the
# composite key itself for entity creation (it is still a valid getattr).
COMPOSITE_FIELD_UNDERLYING: dict[str, tuple[str, ...]] = {
    "rtc": ("_rtc_year", "_rtc_month", "_rtc_day", "_rtc_hour", "_rtc_minute", "_rtc_second"),
}


def restrict_names(served: list[str]) -> list[str]:
    """Expand composite fields into their underlying names for restrict_fields()."""
    out: list[str] = []
    for name in served:
        out.extend(COMPOSITE_FIELD_UNDERLYING.get(name, (name,)))
    return out


# Serial-number-prefix -> (invertertype bitmask, model name), ported verbatim
# from sofar_plugin.async_determineInverterType (plugin_sofar.py). Longer/more
# specific prefixes are listed first so startswith() matching picks them over
# a shorter overlapping prefix (e.g. "SP1ES120N6" before "SP1").
SERIAL_PREFIX_TABLE: tuple[tuple[str, int, str], ...] = (
    ("SP1ES120N6", HYBRID | X3, "HYD20KTL-3P"),
    ("SP1", HYBRID | X3 | GEN | BAT_BTS, "HYDxxKTL-3P"),
    ("SP2", HYBRID | X3 | GEN | BAT_BTS, "HYDxxKTL-3P 2nd"),  # model gets a serial-derived suffix, see below
    ("ZP1", HYBRID | X3 | GEN, "HYDxx ZSS"),
    ("ZP2", HYBRID | X3 | GEN, "HYDxx ZSS"),
    ("SM2E", HYBRID | X1 | GEN, "HYDxxxxES"),
    ("ZM2E", HYBRID | X1 | GEN, "HYDxxxxKTL ZCS HP"),
    ("SH3E", PV | X1 | GEN, "4.6 KTLM-G3"),
    ("SS2E", PV | X3 | GEN, "4.4 KTLX-G3"),
    ("ZS2E", PV | X3 | GEN, "12 Azzurro KTL-V3"),
    ("SQ1ES1", PV | X3 | GEN | MPPT10, "100kW KTLX-G4"),
    ("SA1", PV | X1, ""),
    ("SB1", PV | X1, ""),
    ("SC1", PV | X3, ""),
    ("SD1", PV | X3, ""),
    ("SF4", PV | X3, ""),
    ("SH1", HYBRID | X3 | GEN | BAT_BTS, "HYD5...8KTL-3P"),
    ("SL1", PV | X3, ""),
    ("SJ2", PV | X3, ""),
    ("SS1", PV | X3 | GEN, ""),
)


def determine_inverter_type(serial: str) -> tuple[int, str]:
    """Return (invertertype bitmask, model name) for a Sofar serial number.

    0 / "" means the prefix table has no match — an unrecognized inverter.
    """
    for prefix, invertertype, model in SERIAL_PREFIX_TABLE:
        if serial.startswith(prefix):
            if prefix == "SP2" and len(serial) >= 8:
                model = f"HYD{serial[6:8]}KTL-3P 2nd"
            return invertertype, model
    return 0, ""

