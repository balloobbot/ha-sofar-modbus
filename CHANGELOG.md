# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows
[Semantic Versioning](https://semver.org/) — while the major version is `0`, a `MINOR` bump
means new user-facing capability (a new platform, new entities reachable from Home Assistant),
a `PATCH` bump means a fix with no new capability. Each version bump gets a matching git tag
and GitHub Release.

## [Unreleased]

### Added

- `parallel_address`, `remote_switch_on_off`, `charger_use_mode` marked `writable=True` at the
  `Component` level, and excluded from the generated read-only sensor list — groundwork for the
  number/select write entities, not yet built. No new entity or behavior is reachable from Home
  Assistant yet.

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
