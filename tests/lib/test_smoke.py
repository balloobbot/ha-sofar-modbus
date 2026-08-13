"""Smoke test: setup -> SofarInverter -> entity filtering -> read every served
field, against the mock backend, for both a PV-only and a HYBRID identity.

Not a full pytest suite yet (that's tracked separately) — this is the
end-to-end check generated_sensors.py's component mapping is validated
against during development. Safe to run standalone:
`python tests/lib/test_smoke.py`.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "custom_components" / "sofar_modbus"))

from generated_sensors import SENSOR_DESCRIPTIONS  # noqa: E402
from modbus_connection.mock import MockModbusConnection  # noqa: E402
from sofar_modbus.model import SofarComponentBase  # noqa: E402
from sofar_modbus.modern.device import SofarInverter  # noqa: E402


def _check_all_descriptions_resolve() -> None:
    """Every (component, key) row must resolve to a real attribute on
    SofarInverter, regardless of which identity would poll it — catches a
    wrong entry in generate_sofar_model.py's component mapping that the
    PV/HYBRID runs below wouldn't exercise on their own (e.g. an EPS- or
    MPPT-only field neither test identity serves).
    """
    device = SofarInverter.__new__(SofarInverter)
    SofarInverter.__init__(device, unit=None)  # type: ignore[arg-type]
    bad: list[str] = []
    for description in SENSOR_DESCRIPTIONS:
        component = getattr(device, description.component, None)
        if component is None or not hasattr(component, description.key):
            bad.append(f"{description.component}.{description.key}")
    assert not bad, f"SENSOR_DESCRIPTIONS references missing attributes: {bad}"
    print(f"all {len(SENSOR_DESCRIPTIONS)} sensor rows resolve to real attributes")


def _seed_serial(unit: object, serial: str) -> dict[int, int]:
    regs: dict[int, int] = {}
    padded = serial.ljust(14, "\x00")
    for i in range(7):
        hi, lo = ord(padded[2 * i]), ord(padded[2 * i + 1])
        regs[0x445 + i] = (hi << 8) | lo
    unit.load_raw({"holding": regs})  # type: ignore[attr-defined]
    return regs


async def _run(serial: str, label: str) -> int:
    conn = MockModbusConnection()
    unit = conn.for_unit(1)
    seeded = _seed_serial(unit, serial)

    device = SofarInverter(unit)
    await device.async_setup()
    print(f"[{label}] serial={device.serial_number} model={device.model} type={device.inverter_type!r}")

    # No public "what will be polled" surface — seed every component's
    # fields regardless of whether this inverter type actually serves it;
    # an unpolled component's registers are simply never read.
    all_regs = dict(seeded)
    for comp in vars(device).values():
        if not isinstance(comp, SofarComponentBase):
            continue
        for _name, field in type(comp).declared_fields.items():
            addr = getattr(field, "address", None)
            if addr is not None:
                all_regs.setdefault(addr, 1)
    unit.load_raw({"holding": all_regs})

    report = await device.async_update()
    assert report.complete, f"unexpected failures against the mock backend: {report.failed}"
    served = report.updated | set(report.failed)  # every component this poll attempted

    built = 0
    skipped = 0
    for description in SENSOR_DESCRIPTIONS:
        if description.component not in served:
            skipped += 1
            continue
        component = getattr(device, description.component)
        getattr(component, description.key)  # must not raise
        built += 1
    print(f"[{label}] {built} entities built, {skipped} skipped (unserved by this inverter type)")
    assert built > 0
    return built


async def main() -> None:
    _check_all_descriptions_resolve()

    pv_built = await _run("SS2ES104N5S445", "PV (live hardware serial)")
    hybrid_built = await _run("SP1XXES100XX", "HYBRID (SP1 prefix)")
    # Regression guard: a PV inverter must end up with meaningfully fewer
    # entities than a HYBRID one (battery, EPS, passive mode etc. are
    # HYBRID-only), not "nearly everything" for both.
    assert pv_built < hybrid_built * 0.8, (
        f"PV ({pv_built}) should be well below HYBRID ({hybrid_built}) — component filtering may not be applying"
    )
    print("SMOKE TEST PASSED")


if __name__ == "__main__":
    asyncio.run(main())
