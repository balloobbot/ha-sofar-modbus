#!/usr/bin/env python3
"""Generate the SENSOR_DESCRIPTIONS tail of custom_components/sofar_modbus/sensor.py
from upstream plugin_sofar.py.

Pipeline: extract_sofar_ast.py walks the upstream source with `ast` (no
homeassistant import needed) and hands back plain-dict entity descriptions.
This script turns those into HA SensorEntityDescription rows, tagging each
with the sofar_modbus library component that serves it.

sensor.py is a merged file: a hand-written head (imports, async_setup_entry,
SofarSensor) and a generated tail (SofarSensorDescription, SENSOR_DESCRIPTIONS),
split by the "# GENERATOR: generated below" marker. This script only replaces
the tail — the hand-written head, including the full import block (which must
stay at the top of the file; the generated content's own imports live there
too, so there's one import block, not two), is read from the existing file and
kept verbatim.

The register/decode logic itself is no longer generated here — it lives in
the `sofar-modbus` dependency (github.com/darkrain-nl/sofar-modbus). This
script only maps each field key to the SofarInverter attribute that holds it,
introspected from the installed library, and emits the HA-facing metadata
(name, device_class, unit, icon, category) that the library doesn't carry —
only when it differs from the dataclass's own default, so a row doesn't spell
out every field HA already defaults for it.

Re-run whenever plugin_sofar.py is updated upstream; output is checked in,
never imported at runtime by the generator itself.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from collections.abc import Iterator
from enum import IntEnum
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
import extract_sofar_ast as ex  # noqa: E402

REPO_ROOT = Path(__file__).parent.parent
SENSOR_PY = REPO_ROOT / "custom_components" / "sofar_modbus" / "sensor.py"

UPSTREAM_REPO = Path("/home/darkrain/homeassistant/homeassistant-solax-modbus")

_GENERATED_MARKER = "# GENERATOR: generated below"


def upstream_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(UPSTREAM_REPO), "rev-parse", "--short", "HEAD"], text=True
        ).strip()
    except Exception:
        return "unknown"


# Settings-area fields the device writes directly (upstream write_method=
# WRITE_MULTISINGLE_MODBUS — a single register written via FC16, not FC06).
# A future number/select platform would write straight through the library's
# async_write_* helpers; no local-storage entity needed since these have a
# real backing register. Not built yet — see CHANGELOG.
WRITABLE_FIELDS: set[str] = {"parallel_address", "remote_switch_on_off", "charger_use_mode"}

# generated_sensors.py must not also emit a read-only sensor for a key that
# would get a number/select entity instead — one entity per key, matching
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

# Component-level @property fields (computed from underlying registers) that
# Component.declared_fields doesn't know about, since they aren't field
# descriptors. Identity.rtc is the only one that reaches a sensor here — the
# battery tower (BatteryPack.pack_time, same pattern) is excluded entirely,
# see build_component_of().
_COMPUTED_PROPERTY_FIELDS: dict[str, str] = {"rtc": "identity"}

# HA's own default for each optional SensorEntityDescription/EntityDescription
# field, as source text — checked against homeassistant/components/sensor/__init__.py
# and homeassistant/helpers/entity.py directly. A row only spells out a field
# when its value differs from this.
_DEFAULTS: dict[str, str] = {
    "device_class": "None",
    "native_unit_of_measurement": "None",
    "state_class": "None",
    "entity_category": "None",
    "icon": "None",
    "entity_registry_enabled_default": "True",
}


def _iter_declared_fields() -> Iterator[tuple[str, str, Any]]:
    """Yield (key, component attr, field) for every declared field on every
    polled component, from a throwaway SofarInverter (construction does no
    I/O — see connection.py). One source of truth for both the key->component
    mapping below and the key->enum-type mapping in build_enum_of(), instead
    of two throwaway devices built the same way.

    Deliberately excludes BatteryPack: sofar_modbus.modern.device.SofarInverter
    leaves it out of polled_components on purpose (its packs share one
    register block and are read one at a time via async_read_pack(), not as
    part of the regular poll) — so a battery_pack-sourced sensor row could
    never be served under the polled-components model sensor.py uses. Battery
    tower support needs its own pack-selection entity, not a plain sensor;
    that's future work alongside the writable settings in CONTROL_ONLY_KEYS.
    """
    import sofar_modbus.modern.device as dev
    from sofar_modbus.model import SofarComponentBase

    device = dev.SofarInverter.__new__(dev.SofarInverter)
    dev.SofarInverter.__init__(device, unit=None)  # type: ignore[arg-type]

    for attr, value in vars(device).items():
        if attr == "battery_pack" or not isinstance(value, SofarComponentBase):
            continue
        for key, field in type(value).declared_fields.items():
            yield key, attr, field


def build_component_of() -> dict[str, str]:
    """field key -> SofarInverter attribute, from the library's own declared_fields."""
    component_of: dict[str, str] = dict(_COMPUTED_PROPERTY_FIELDS)
    for key, attr, _field in _iter_declared_fields():
        component_of[key] = attr
    return component_of


def build_enum_of() -> dict[str, type[IntEnum]]:
    """field key -> its IntEnum type, for fields whose raw value needs a text
    label rather than showing as a bare number — Python 3.11 changed
    IntEnum.__str__ to print just the int, unlike plain Enum.

    IntFlag fields (the Fault1-12 bitmasks, PowerControlFlags) are skipped
    automatically: IntFlag does not subclass IntEnum, so issubclass() below
    never matches them — leave their current rendering alone.
    """
    enum_of: dict[str, type[IntEnum]] = {}
    for key, _attr, field in _iter_declared_fields():
        convert = getattr(field, "convert", None)
        if isinstance(convert, type) and issubclass(convert, IntEnum):
            enum_of[key] = convert
    return enum_of


def _enum_label(member_name: str) -> str:
    """Title-Case a SCREAMING_SNAKE_CASE enum member name for display —
    e.g. "GRID_CONNECTED" -> "Grid Connected". Mechanical, not matching
    upstream's own hand-picked strings (its `scale` kwarg — a raw-int-to-string
    dict, not a real SensorEntityDescription field, so it's never extracted).
    Same style as select.py's hand-written _XXX_OPTIONS dicts elsewhere in
    this integration.
    """
    return " ".join(word.capitalize() for word in member_name.split("_"))


def sanitize_key(key: str) -> str:
    """Fix the handful of upstream keys that aren't valid identifiers.

    e.g. "reactive Power_output_total" (an upstream typo — a stray space)
    becomes "reactive_power_output_total".
    """
    return key.replace(" ", "_").lower()


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


def _optional_kwarg_line(entry: dict[str, Any], field: str) -> str | None:
    """Source line for one optional kwarg, or None if it matches HA's own default."""
    default = _DEFAULTS[field]
    src = entry_field_src(entry, field, default)
    return None if src == default else f"        {field}={src},"


_TAIL_TEMPLATE = '''# GENERATOR: generated below from plugin_sofar.py @ {commit} by
# scripts/generate_sofar_model.py — do not hand-edit past this line.


@dataclass(frozen=True, kw_only=True)
class SofarSensorDescription(SensorEntityDescription):
    """A real SensorEntityDescription, plus which Component the value comes from.

    Must subclass SensorEntityDescription (not just duck-type its fields) —
    SensorEntity reads attributes like entity_registry_visible_default and
    suggested_unit_of_measurement straight off entity_description with no
    _attr_ fallback, so a bespoke dataclass raises AttributeError on those.
    """

    component: str  # attribute name on SofarInverter, e.g. 'grid', 'pv_1_2', 'energy'


SENSOR_DESCRIPTIONS: tuple[SofarSensorDescription, ...] = (\
'''


def gen_sensor_descriptions(
    entries: list[dict[str, Any]], component_of: dict[str, str], enum_of: dict[str, type[IntEnum]], commit: str
) -> str:
    lines = [_TAIL_TEMPLATE.format(commit=commit)]

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

        if key not in component_of:
            raise KeyError(f"{key!r} has no sofar_modbus component — field renamed upstream or in the library?")

        lines.append("    SofarSensorDescription(")
        lines.append(f"        key={key!r},")
        lines.append(f"        component={component_of[key]!r},")
        lines.append(f"        name={entry_field_src(entry, 'name')},")

        # Enum-typed fields get their device_class/options from the library's
        # own type, not from upstream's `scale` dict (not a real
        # SensorEntityDescription field, so entry_field_src never sees it).
        enum_type = enum_of.get(key)
        if enum_type is not None:
            lines.append("        device_class=SensorDeviceClass.ENUM,")
            options = [_enum_label(member.name) for member in enum_type]
            lines.append(f"        options={py_repr(options)},")

        for field in (
            "device_class",
            "native_unit_of_measurement",
            "state_class",
            "entity_category",
            "icon",
            "entity_registry_enabled_default",
        ):
            if field == "device_class" and enum_type is not None:
                continue  # already emitted above, from the library's own enum type
            optional_line = _optional_kwarg_line(entry, field)
            if optional_line is not None:
                lines.append(optional_line)
        rounding = entry.get("rounding", {}).get("value")
        if isinstance(rounding, int) and rounding != 1:
            lines.append(f"        suggested_display_precision={rounding},")
        lines.append("    ),")

    lines.append(")")
    return "\n".join(lines) + "\n"


def merged_sensor_py(tail: str) -> str:
    """The hand-written head of sensor.py, verbatim, plus the freshly generated tail."""
    current = SENSOR_PY.read_text()
    marker_index = current.find(_GENERATED_MARKER)
    if marker_index == -1:
        raise ValueError(
            f"{SENSOR_PY} has no {_GENERATED_MARKER!r} marker — can't tell where the "
            "hand-written head ends and the generated tail begins"
        )
    return current[:marker_index] + tail


def main() -> None:
    commit = upstream_commit()
    tree = ast.parse(ex.UPSTREAM.read_text())

    # BATTERY_SENSOR_TYPES (the BTS tower) is deliberately excluded — see
    # build_component_of()'s docstring.
    sensors = ex.extract_list(tree, "SENSOR_TYPES") or []

    component_of = build_component_of()
    enum_of = build_enum_of()
    tail = gen_sensor_descriptions(sensors, component_of, enum_of, commit)
    SENSOR_PY.write_text(merged_sensor_py(tail))

    print(f"sensor rows: {tail.count('SofarSensorDescription(')}", file=sys.stderr)
    print(f"upstream commit: {commit}", file=sys.stderr)

    subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--fix", "--quiet", str(SENSOR_PY)],
        cwd=REPO_ROOT,
        check=False,
    )


if __name__ == "__main__":
    main()
