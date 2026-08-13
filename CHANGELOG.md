# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows
[Semantic Versioning](https://semver.org/) — while the major version is `0`, a `MINOR` bump
means new user-facing capability (a new platform, new entities reachable from Home Assistant),
a `PATCH` bump means a fix with no new capability. Each version bump gets a matching git tag
and GitHub Release.

## [Unreleased]

## [0.1.6] - 2026-08-13

### Changed

- Replaced the vendored `sofar/` device library (extracted from `homeassistant-solax-modbus`'s
  `plugin_sofar.py`, hand-debugged through 0.1.1–0.1.5) with the
  [`sofar-modbus`](https://github.com/darkrain-nl/sofar-modbus) dependency, pinned to `v0.1.0` via
  `git+https` (not yet on PyPI). It's a fork of an independently-built library on the same
  `modbus-connection` foundation, covering the same register map but split per register-block
  instead of one monolithic component — so it doesn't have the vendored code's `max_span`/
  scale-factor bug classes ([0.1.4], [0.1.5]) by construction. `custom_components/sofar_modbus/sofar/`
  and its two dedicated guard tests (`test_no_ha_imports.py`, `test_field_scales.py`) are gone; the
  equivalent guards now live in the library's own test suite.
- `config_flow.py`/`__init__.py` moved from the vendored two-phase `async_probe()` (raising on an
  unrecognized serial) to the library's single-phase `SofarInverter(unit)` + `async_setup()` (which
  leaves `.inverter_type` at zero instead of raising). A new local `probe.py` restores the same
  `SofarUnrecognizedError` contract on top.
- `generated_sensors.py`'s `component=` values now point at the library's ~20 per-register-block
  attributes (`grid`, `pv_1_2`, `energy`, …) instead of the vendored `realtime`/`settings`/
  `battery_pack` split. `scripts/generate_sofar_model.py` derives that mapping by introspecting the
  installed library instead of generating the register/decode layer itself — the script only emits
  HA-facing `SensorEntityDescription` metadata now.
- `sensor.py`'s serving check is now `component in device.polled_components` (per-component) instead
  of the vendored per-field `*_served_keys` sets — verified to produce an identical entity count for
  both a PV-only and a synthetic HYBRID identity via the updated `tests/lib/test_smoke.py`.

### Removed

- The BTS battery-tower sensor rows (17 fields, upstream `BATTERY_SENSOR_TYPES`): the library
  deliberately excludes the tower from its regular poll (`polled_components`) since its packs share
  one register block and are read one at a time via `async_read_pack()`, not as part of a normal
  update cycle. No live device serves these today; a battery-pack platform needs its own
  pack-selection entity as a follow-up, not a plain sensor.

### Note

- Supersedes the `writable=True` groundwork from the previous unreleased entry: the library already
  ships `parallel_address`/`remote_switch_on_off`/`charger_use_mode` as `writable=True`, plus
  `async_write_*` convenience methods for feed-in limit, EPS control, passive-mode setpoints, RTC,
  and an IV-curve-scan trigger. A number/select write platform is a smaller follow-up than
  originally scoped, still not built in this release.

## [0.1.5] - 2026-08-12

### Fixed

- `Component.max_span` capped at 48 registers on all three generated components, matching
  upstream `plugin_sofar.py`'s `block_size=48`. The library's 125-register default produced
  46- and 57-register block reads that timed out consistently against the real inverter's
  Modbus TCP gateway.

## [0.1.4] - 2026-08-12

### Fixed

- 32-bit register fields (`solar_generation_today`/`_total`, `load_consumption_*`,
  `import_energy_*`, `export_energy_*`, `battery_input_energy_*`, `battery_output_energy_*`)
  were silently losing their scale factor — the generator returned `uint32`/`int32` before the
  scale check ever ran, so these decoded as raw register counts (10x-100x too large). Caught by
  comparing live values against `homeassistant-solax-modbus` on the same inverter.

## [0.1.3] - 2026-08-12

### Fixed

- Entity filtering was checking `description.key not in component.declared_fields`, but
  `Component.restrict_fields()` deliberately leaves `declared_fields` describing the full
  static layout regardless of what was excluded (an excluded field just decodes to `None`).
  This meant nearly every generated sensor got an entity regardless of inverter type — 236 of
  254 possible sensors on a PV-only inverter instead of the correct 89. `SofarInverter` now
  records the actual per-inverter-type served-field sets separately for entity platforms to
  filter against.

## [0.1.2] - 2026-08-12

### Fixed

- Every sensor entity failed to set up with `AttributeError` on `entity_registry_visible_default`
  and `suggested_unit_of_measurement`. `SofarSensorDescription` was a bespoke dataclass
  duck-typing a few `SensorEntityDescription` fields; `SensorEntity` reads several other
  attributes straight off `entity_description` with no `_attr_` fallback. Now a real
  `SensorEntityDescription` subclass.

## [0.1.1] - 2026-08-12

### Fixed

- Reverted an in-flight switch to the `pymodbus` backend back to `tmodbus` (the intended
  backend). The switch had been a workaround for `homeassistant-solax-modbus`'s exact
  `tmodbus==0.4.1` pin conflicting with this integration's `tmodbus>=0.5.1` requirement, but
  that pin gets re-applied on every Home Assistant restart while `solax_modbus` is loaded, so
  changing backends only masked the conflict. Documented instead: don't run this alongside
  `solax_modbus` on the same Home Assistant instance.

## [0.1.0] - 2026-08-12

### Added

- Initial release. Read-only sensor platform (TCP only) for Sofar inverters, built on
  [`modbus-connection`](https://github.com/home-assistant-libs/modbus-connection) instead of a
  hand-rolled Modbus hub. Register map and entity descriptions generated from upstream
  `homeassistant-solax-modbus`'s `plugin_sofar.py` via `scripts/generate_sofar_model.py`.
  Config flow probes the inverter's serial number to classify the model and determine which
  registers it serves.
