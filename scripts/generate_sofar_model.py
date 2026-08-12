#!/usr/bin/env python3
"""Generate the Sofar device library from upstream plugin_sofar.py.

Pipeline: extract_sofar_ast.py walks the upstream source with `ast` (no
homeassistant import needed) and hands back plain-dict entity descriptions.
This script turns those into:

  - sofar/components/realtime.py   Component: 0x404-0x6FF real-time telemetry
  - sofar/components/settings.py   Component: 0x1000-0x11FF settings readback
  - sofar/components/battery_pack.py  Component: 0x900x battery-pack data (BAT_BTS)
  - sofar/const.py                 bitmasks, per-field allowedtypes tables
  - custom_components/sofar_modbus/generated_sensors.py   HA SensorEntityDescription rows

Re-run whenever plugin_sofar.py is updated upstream; output is checked in,
never imported at runtime by the generator itself. Pin the upstream commit
this was run against in UPSTREAM_COMMIT below.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
import extract_sofar_ast as ex  # noqa: E402

REPO_ROOT = Path(__file__).parent.parent
SOFAR_LIB = REPO_ROOT / "custom_components" / "sofar_modbus" / "sofar"
GENERATED_ENTITIES = REPO_ROOT / "custom_components" / "sofar_modbus" / "generated_sensors.py"

UPSTREAM_REPO = Path("/home/darkrain/homeassistant/homeassistant-solax-modbus")


def upstream_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(UPSTREAM_REPO), "rev-parse", "--short", "HEAD"], text=True
        ).strip()
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
# value_function-backed sensors that need hand-written decoding instead of a
# mechanical scale/register_data_type translation. Keyed by `key`.
# ---------------------------------------------------------------------------
HANDWRITTEN_FIELDS: set[str] = {"rtc", "battery_active_control", "parallel_control"}

# Settings-area fields the device writes directly (upstream write_method=
# WRITE_MULTISINGLE_MODBUS — a single register written via FC16, not FC06).
# number.py/select.py write straight through component.write(key, value);
# no local-storage entity needed since these have a real backing register.
WRITABLE_FIELDS: set[str] = {"parallel_address", "remote_switch_on_off", "charger_use_mode"}

# generated_sensors.py must not also emit a read-only sensor for a key that
# gets a number/select entity instead — one entity per key, matching
# upstream (a select's "current value" reads the same field directly).
# Superset of WRITABLE_FIELDS: also covers WRITE_DATA_LOCAL selects whose
# readback sensor shares their key (feedin_limitation_mode, eps_control,
# passive_mode_timeout, passive_mode_timeout_action).
CONTROL_ONLY_KEYS: set[str] = WRITABLE_FIELDS | {
    "feedin_limitation_mode",
    "eps_control",
    "passive_mode_timeout",
    "passive_mode_timeout_action",
}


def sanitize_key(key: str) -> str:
    """Fix the handful of upstream keys that aren't valid identifiers.

    e.g. "reactive Power_output_total" (an upstream typo — a stray space)
    becomes "reactive_power_output_total".
    """
    return key.replace(" ", "_").lower()

HEADER = '''"""Generated from plugin_sofar.py @ {commit} by scripts/generate_sofar_model.py.

Do not hand-edit — re-run the generator instead. See scripts/generate_sofar_model.py
for the translation rules.
"""

from __future__ import annotations

from modbus_connection.model import Component, NumberField, gauge, int32, integer, string, uint32

'''


def py_repr(value: Any) -> str:
    return repr(value)


def entry_field_src(entry: dict[str, Any], field: str, default: str = "None") -> str:
    """Source text for one extracted kwarg: a literal repr, or verbatim expression text."""
    v = entry.get(field)
    if v is None:
        return default
    if v["kind"] == "literal":
        return py_repr(v["value"])
    return v["value"]  # source text, e.g. "SensorDeviceClass.POWER"


def field_call(entry: dict[str, Any]) -> tuple[str, int]:
    """Return (source expression, register address) for one entity's field."""
    reg = entry["register"]["value"]
    rdt = entry.get("register_data_type", {}).get("value", "REGISTER_U16")
    scale_kind = entry.get("scale", {}).get("kind")
    signed = rdt in ("REGISTER_S16", "REGISTER_S32")
    key = sanitize_key(entry["key"]["value"])
    # WRITE_MULTISINGLE_MODBUS upstream: a single register, written via
    # FC16 rather than FC06 — force_fc16=True is the library's equivalent.
    write_kwargs = ", writable=True, force_fc16=True" if key in WRITABLE_FIELDS else ""

    if scale_kind == "dict":
        convert = entry["scale"]["value"]
        # JSON round-trip is not used here (values come straight from AST),
        # so dict keys are already Python ints.
        convert_src = "{" + ", ".join(f"{k!r}: {v!r}" for k, v in convert.items()) + "}"
        return f"NumberField({reg}, signed={signed}, convert={convert_src}{write_kwargs})", reg

    if rdt == "REGISTER_STR":
        count = entry["wordcount"]["value"]
        return f"string({reg}, {count})", reg

    if rdt == "REGISTER_WORDS":
        # handled by HANDWRITTEN_FIELDS instead
        raise ValueError("REGISTER_WORDS must be hand-written")

    scale = entry.get("scale", {}).get("value", 1) if scale_kind == "literal" else 1
    has_scale = isinstance(scale, (int, float)) and scale != 1

    if rdt == "REGISTER_U32":
        return (f"uint32({reg}, scale={scale!r}{write_kwargs})" if has_scale else f"uint32({reg}{write_kwargs})"), reg
    if rdt == "REGISTER_S32":
        return (f"int32({reg}, scale={scale!r}{write_kwargs})" if has_scale else f"int32({reg}{write_kwargs})"), reg

    if has_scale:
        return f"gauge({reg}, {scale!r}, signed={signed}{write_kwargs})", reg
    return f"integer({reg}, signed={signed}{write_kwargs})", reg


def gen_component(class_name: str, entries: list[dict[str, Any]], commit: str) -> tuple[str, dict[str, int]]:
    """Build one Component subclass's source and its field->allowedtypes map."""
    lines = [HEADER.format(commit=commit)]
    lines.append(f"class {class_name}(Component):")
    lines.append(f'    """{len(entries)} fields, generated — see module docstring."""')
    lines.append("")
    # Matches plugin_sofar.py's block_size=48: the real hardware/gateway
    # times out on reads wider than this (seen live: 46- and 57-register
    # blocks under the library's 125-register default failed consistently).
    lines.append("    max_span = 48")
    lines.append("")

    allowedtypes: dict[str, int] = {}
    seen_keys: dict[str, int] = {}  # key -> register, to dedupe repeated declarations
    ordered_keys: list[str] = []

    for entry in entries:
        raw_key = entry["key"]["value"]
        if "{}" in raw_key:
            # value_series-templated field (e.g. "cell_{}_voltage") — the
            # per-index register stride isn't recoverable from one static
            # entry. Battery-pack detail is Phase 4 / best-effort; skip here.
            print(f"skipping templated key {raw_key!r} (value_series field)", file=sys.stderr)
            continue
        key = sanitize_key(raw_key)
        mask = entry.get("allowedtypes", {}).get("value", 0)
        if key in seen_keys:
            allowedtypes[key] |= mask
            continue
        seen_keys[key] = entry["register"]["value"]
        ordered_keys.append(key)
        allowedtypes[key] = mask

        if key in HANDWRITTEN_FIELDS:
            continue

        expr, reg = field_call(entry)
        mask_src = entry.get("allowedtypes", {}).get("source", "ALLDEFAULT")
        comment = f"  # 0x{reg:04X}, allowedtypes={mask_src}"
        if entry.get("internal", {}).get("value"):
            comment += ", internal"
        lines.append(f"    {key} = {expr}{comment}")

    # hand-written sub-fields + computed properties
    if "rtc" in seen_keys:
        base = seen_keys["rtc"]
        lines.append("")
        lines.append("    # rtc: REGISTER_WORDS(6) — y/m/d/h/mi/s, one register each")
        for i, part in enumerate(("_rtc_year", "_rtc_month", "_rtc_day", "_rtc_hour", "_rtc_minute", "_rtc_second")):
            lines.append(f"    {part} = integer({base + i}, signed=False)")
        lines.append("")
        lines.append("    @property")
        lines.append("    def rtc(self) -> str | None:")
        lines.append('        """Inverter RTC as "DD/MM/YY HH:MM:SS", or None if unreadable."""')
        lines.append(
            "        parts = (self._rtc_day, self._rtc_month, self._rtc_year, self._rtc_hour, self._rtc_minute, self._rtc_second)"
        )
        lines.append("        if any(p is None for p in parts):")
        lines.append("            return None")
        lines.append("        d, mo, y, h, mi, s = parts")
        lines.append('        return f"{d:02}/{mo:02}/{y % 100:02} {h:02}:{mi:02}:{s:02}"')

    if "battery_active_control" in seen_keys or "parallel_control" in seen_keys:
        lines.append("")
        lines.append("    # value_function_disabled_enabled: 0/1 -> Disabled/Enabled")
        for key in ("battery_active_control", "parallel_control"):
            if key in seen_keys:
                reg = seen_keys[key]
                lines.append(f'    {key} = NumberField({reg}, signed=False, convert={{0: "Disabled", 1: "Enabled"}})')

    src = "\n".join(lines) + "\n"
    return src, allowedtypes


def gen_const(realtime_types: dict[str, int], settings_types: dict[str, int], battery_types: dict[str, int], commit: str) -> str:
    lines = [
        f'"""Generated from plugin_sofar.py @ {commit}. Bitmasks and per-field allowedtypes.\n\n'
        'Do not hand-edit — re-run scripts/generate_sofar_model.py.\n"""\n',
        "from __future__ import annotations\n",
    ]
    lines.append("# -- inverter-type bitmasks (ported verbatim from plugin_sofar.py) --------")
    for name, value in ex.BITMASKS.items():
        lines.append(f"{name} = 0x{value:X}" if value else f"{name} = 0")
    lines.append("")
    lines.append("# -- per-field allowedtypes, by component -----------------------------------")
    for var, table in (
        ("REALTIME_ALLOWEDTYPES", realtime_types),
        ("SETTINGS_ALLOWEDTYPES", settings_types),
        ("BATTERY_PACK_ALLOWEDTYPES", battery_types),
    ):
        lines.append(f"{var}: dict[str, int] = {{")
        for k, v in table.items():
            lines.append(f"    {k!r}: 0x{v:X},")
        lines.append("}")
        lines.append("")

    lines.append('''
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
''')
    return "\n".join(lines) + "\n"


def gen_sensor_descriptions(entries: list[dict[str, Any]], component_of: dict[str, str], commit: str) -> str:
    lines = [
        f'"""Generated HA sensor metadata from plugin_sofar.py @ {commit}.\n\n'
        'Do not hand-edit — re-run scripts/generate_sofar_model.py. Rows with\n'
        '`internal=True` back computed values only and have no `key` here.\n"""\n',
        "from __future__ import annotations\n",
        "from dataclasses import dataclass\n",
        "from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription, SensorStateClass",
        "from homeassistant.const import (",
        "    PERCENTAGE,",
        "    UnitOfApparentPower,",
        "    UnitOfElectricCurrent,",
        "    UnitOfElectricPotential,",
        "    UnitOfEnergy,",
        "    UnitOfFrequency,",
        "    UnitOfPower,",
        "    UnitOfReactivePower,",
        "    UnitOfTemperature,",
        "    UnitOfTime,",
        ")",
        "from homeassistant.helpers.entity import EntityCategory",
        "",
        "",
        "@dataclass(frozen=True, kw_only=True)",
        "class SofarSensorDescription(SensorEntityDescription):",
        '    """A real SensorEntityDescription, plus which Component the value comes from.',
        "",
        '    Must subclass SensorEntityDescription (not just duck-type its fields) —',
        "    SensorEntity reads attributes like entity_registry_visible_default and",
        '    suggested_unit_of_measurement straight off entity_description with no',
        '    _attr_ fallback, so a bespoke dataclass raises AttributeError on those.',
        '    """',
        "",
        "    component: str = 'realtime'  # attribute name on SofarInverter: 'realtime' | 'settings' | 'battery_pack'",
        "",
        "",
        "SENSOR_DESCRIPTIONS: tuple[SofarSensorDescription, ...] = (",
    ]

    seen: set[str] = set()
    for entry in entries:
        raw_key = entry["key"]["value"]
        if "{}" in raw_key:
            continue
        key = sanitize_key(raw_key)
        if key in seen or entry.get("internal", {}).get("value") or key in CONTROL_ONLY_KEYS:
            seen.add(key)
            continue
        seen.add(key)

        rounding = entry.get("rounding", {}).get("value")
        precision = str(rounding) if isinstance(rounding, int) and rounding != 1 else "None"

        lines.append("    SofarSensorDescription(")
        lines.append(f"        key={key!r},")
        lines.append(f"        component={component_of.get(key, 'realtime')!r},")
        lines.append(f"        name={entry_field_src(entry, 'name')},")
        lines.append(f"        device_class={entry_field_src(entry, 'device_class')},")
        lines.append(f"        native_unit_of_measurement={entry_field_src(entry, 'native_unit_of_measurement')},")
        lines.append(f"        state_class={entry_field_src(entry, 'state_class')},")
        lines.append(f"        entity_category={entry_field_src(entry, 'entity_category')},")
        lines.append(f"        icon={entry_field_src(entry, 'icon')},")
        lines.append(
            f"        entity_registry_enabled_default={entry_field_src(entry, 'entity_registry_enabled_default', 'True')},"
        )
        lines.append(f"        suggested_display_precision={precision},")
        lines.append("    ),")

    lines.append(")")
    return "\n".join(lines) + "\n"


def main() -> None:
    commit = upstream_commit()
    tree = ast.parse(ex.UPSTREAM.read_text())

    sensors = ex.extract_list(tree, "SENSOR_TYPES") or []
    battery_sensors = ex.extract_list(tree, "BATTERY_SENSOR_TYPES") or []

    realtime_entries = [e for e in sensors if e["register"]["value"] < 0x1000]
    settings_entries = [e for e in sensors if e["register"]["value"] >= 0x1000]

    SOFAR_LIB.mkdir(parents=True, exist_ok=True)
    (SOFAR_LIB / "components").mkdir(parents=True, exist_ok=True)
    (SOFAR_LIB / "__init__.py").write_text('"""Sofar device library — no homeassistant import allowed here."""\n')
    (SOFAR_LIB / "components" / "__init__.py").write_text("")

    realtime_src, realtime_types = gen_component("RealtimeData", realtime_entries, commit)
    settings_src, settings_types = gen_component("SettingsReadback", settings_entries, commit)
    battery_src, battery_types = gen_component("BatteryPack", battery_sensors, commit)

    (SOFAR_LIB / "components" / "realtime.py").write_text(realtime_src)
    (SOFAR_LIB / "components" / "settings.py").write_text(settings_src)
    (SOFAR_LIB / "components" / "battery_pack.py").write_text(battery_src)

    const_src = gen_const(realtime_types, settings_types, battery_types, commit)
    (SOFAR_LIB / "const.py").write_text(const_src)

    component_of = {k: "realtime" for k in realtime_types} | {k: "settings" for k in settings_types} | {
        k: "battery_pack" for k in battery_types
    }
    entities_src = gen_sensor_descriptions(sensors + battery_sensors, component_of, commit)
    GENERATED_ENTITIES.write_text(entities_src)

    print(f"realtime: {len(realtime_types)} fields", file=sys.stderr)
    print(f"settings: {len(settings_types)} fields", file=sys.stderr)
    print(f"battery_pack: {len(battery_types)} fields", file=sys.stderr)
    print(f"upstream commit: {commit}", file=sys.stderr)

    # Not every component uses every imported field helper (e.g. settings.py
    # has no string/uint32 fields) — let ruff drop the unused imports rather
    # than have the generator track per-file usage itself.
    subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--fix", "--quiet", str(SOFAR_LIB), str(GENERATED_ENTITIES)],
        cwd=REPO_ROOT,
        check=False,
    )


if __name__ == "__main__":
    main()
