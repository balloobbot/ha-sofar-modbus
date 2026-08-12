"""Regression guard: every 32-bit register field the generator knows has a
non-1 scale factor must actually carry it on the generated NumberField.

Caught live: uint32/int32 fields returned before the scale check ever ran
in field_call() (scripts/generate_sofar_model.py), so all 12 energy-total
fields (solar_generation_total etc.) silently decoded as raw register
counts — 10x-100x too large — while every other check (imports, ruff, the
mock-backend smoke test) stayed green, because none of them compare against
a known scale.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "custom_components" / "sofar_modbus"))

from sofar.components.realtime import RealtimeData  # noqa: E402

# key -> expected scale, ported from plugin_sofar.py's SENSOR_TYPES entries
# for these keys (all REGISTER_U32/REGISTER_S32 fields with scale != 1).
EXPECTED_SCALES: dict[str, float] = {
    "solar_generation_today": 0.01,
    "solar_generation_total": 0.1,
    "load_consumption_today": 0.01,
    "load_consumption_total": 0.1,
    "import_energy_today": 0.01,
    "import_energy_total": 0.1,
    "export_energy_today": 0.01,
    "export_energy_total": 0.1,
    "battery_input_energy_today": 0.01,
    "battery_input_energy_total": 0.1,
    "battery_output_energy_today": 0.01,
    "battery_output_energy_total": 0.1,
}


def test_32bit_energy_fields_carry_their_scale() -> None:
    mismatches = []
    for key, expected in EXPECTED_SCALES.items():
        field = RealtimeData.declared_fields[key]
        actual = getattr(field, "scale", None)
        if actual != expected:
            mismatches.append((key, expected, actual))
    assert not mismatches, f"scale factor lost for: {mismatches}"


if __name__ == "__main__":
    test_32bit_energy_fields_carry_their_scale()
    print(f"OK: all {len(EXPECTED_SCALES)} 32-bit energy fields carry their scale factor")
