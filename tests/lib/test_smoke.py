"""Smoke test: setup -> SofarInverter -> entity filtering -> read every served
field, against the mock backend, for both a PV-only and a HYBRID identity.

Not a full pytest suite yet (that's tracked separately) — this is the
end-to-end check sensor.py's SENSOR_DESCRIPTIONS component mapping is
validated against during development. Safe to run standalone:
`python tests/lib/test_smoke.py`.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# sensor.py has package-relative imports (.coordinator, .entity), so unlike
# the old standalone generated_sensors.py it can't be loaded as a bare
# top-level module — import it as part of custom_components.sofar_modbus
# instead, the same way test_coordinator.py/test_diagnostics.py do.
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modbus_connection.mock import MockModbusConnection  # noqa: E402
from sofar_modbus.model import SofarComponentBase  # noqa: E402
from sofar_modbus.modern.device import SofarInverter  # noqa: E402

from custom_components.sofar_modbus.sensor import SENSOR_DESCRIPTIONS  # noqa: E402


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


async def _check_enum_sensor_renders_as_text() -> None:
    """system_state is IntEnum-backed (SystemState); native_value must show a
    label like "Grid Connected", not a bare int — Python 3.11 changed
    IntEnum.__str__ to print just the number, which is what the frontend
    showed before device_class=ENUM/options were wired up. Regression guard
    for that wiring in sensor.py and generate_sofar_model.py.
    """
    from types import SimpleNamespace

    from custom_components.sofar_modbus.sensor import SofarSensor

    unit = MockModbusConnection().for_unit(1)
    _seed_serial(unit, "SS2ES104N5S445")
    unit.holding[0x0404] = 2  # system_state -> GRID_CONNECTED

    device = SofarInverter(unit)
    report = await device.async_update()
    assert "state" in report.updated, f"system_state's component did not refresh: {report.failed}"

    coordinator = SimpleNamespace(device=device, config_entry=SimpleNamespace(title="Test Sofar"))
    description = next(d for d in SENSOR_DESCRIPTIONS if d.key == "system_state")
    entity = SofarSensor(coordinator, description)  # type: ignore[arg-type]
    assert entity.native_value == "Grid Connected", f"expected a text label, got {entity.native_value!r}"
    print("enum-sensor-renders-as-text: PASSED")


async def main() -> None:
    _check_all_descriptions_resolve()
    await _check_enum_sensor_renders_as_text()

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
