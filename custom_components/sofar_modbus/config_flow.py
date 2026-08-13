"""Config flow — TCP only for Phase 1. Probes the device to get its serial
number for the unique_id, per the modbus-connection integration guide.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from modbus_connection import ModbusError

from sofar_modbus.modern.device import SofarInverter

from .connection import build_connection, unit_id
from .const import CONF_MODBUS_ADDR, DEFAULT_MODBUS_ADDR, DEFAULT_NAME, DEFAULT_PORT, DOMAIN
from .probe import SofarUnrecognizedError, async_setup_and_check

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_MODBUS_ADDR, default=DEFAULT_MODBUS_ADDR): int,
    }
)


async def _async_probe(data: dict[str, Any]) -> tuple[str, str | None]:
    """Return (serial, model), or raise ModbusError / SofarUnrecognizedError."""
    connection = build_connection(data)
    try:
        device = SofarInverter(connection.for_unit(unit_id(data)))
        await async_setup_and_check(device)
    finally:
        await connection.close()
    return device.serial_number or "", device.model


class SofarConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Sofar Modbus config flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                serial, model = await _async_probe(user_input)
            except ModbusError:
                errors["base"] = "cannot_connect"
            except SofarUnrecognizedError:
                errors["base"] = "unrecognized_inverter"
            else:
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_configured()
                title = f"{user_input[CONF_NAME]} ({model})" if model else user_input[CONF_NAME]
                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors)
