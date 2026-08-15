"""Integration-level constants — config keys, defaults. Distinct from sofar/const.py,
which holds the device library's bitmasks and register-map tables.
"""

from __future__ import annotations

DOMAIN = "sofar_modbus"
ATTR_MANUFACTURER = "Sofar Solar"

DEFAULT_NAME = "Sofar"
DEFAULT_PORT = 502
DEFAULT_MODBUS_ADDR = 1
DEFAULT_SCAN_INTERVAL = 5  # seconds — verified genuinely-fresh (not duplicated) on real hardware; see CHANGELOG

CONF_MODBUS_ADDR = "modbus_addr"
CONF_READ_EPS = "read_eps"
