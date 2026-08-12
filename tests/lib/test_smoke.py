"""Smoke test: probe -> SofarInverter -> entity filtering -> read every served
field, against the mock backend, for both a PV-only and a HYBRID identity.

Not a full pytest suite yet (that's tracked separately) — this is the
end-to-end check the generator's output was validated against during
development. Safe to run standalone: `python tests/lib/test_smoke.py`.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "custom_components" / "sofar_modbus"))

from generated_sensors import SENSOR_DESCRIPTIONS  # noqa: E402
from modbus_connection.mock import MockModbusConnection  # noqa: E402
from sofar.device import SofarInverter, async_probe  # noqa: E402


def _seed_serial(unit: object, serial: str) -> dict[int, int]:
    regs: dict[int, int] = {}
    padded = serial.ljust(14, "\x00")
    for i in range(7):
        hi, lo = ord(padded[2 * i]), ord(padded[2 * i + 1])
        regs[0x445 + i] = (hi << 8) | lo
    unit.load_raw({"holding": regs})  # type: ignore[attr-defined]
    return regs


async def _run(serial: str, label: str) -> None:
    conn = MockModbusConnection()
    unit = conn.for_unit(1)
    seeded = _seed_serial(unit, serial)

    identity = await async_probe(unit)
    print(f"[{label}] identity: {identity}")

    device = SofarInverter(unit, identity)

    all_regs = dict(seeded)
    for comp in (device.realtime, device.settings, device.battery_pack):
        if comp is None:
            continue
        for _name, field in comp.declared_fields.items():
            addr = getattr(field, "address", None)
            if addr is not None:
                all_regs.setdefault(addr, 1)
    unit.load_raw({"holding": all_regs})

    await device.async_update()

    built = 0
    skipped = 0
    for description in SENSOR_DESCRIPTIONS:
        component = getattr(device, description.component, None)
        if component is None:
            skipped += 1
            continue
        if description.key not in component.declared_fields:
            skipped += 1
            continue
        getattr(component, description.key)  # must not raise
        built += 1
    print(f"[{label}] {built} entities built, {skipped} skipped (unserved by this inverter type)")
    assert built > 0


async def main() -> None:
    await _run("SS2ES104N5S445", "PV (live hardware serial)")
    await _run("SP1XXES100XX", "HYBRID (SP1 prefix)")
    print("SMOKE TEST PASSED")


if __name__ == "__main__":
    asyncio.run(main())
