# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows
[Semantic Versioning](https://semver.org/) — while the major version is `0`, a `MINOR` bump
means new user-facing capability (a new platform, new entities reachable from Home Assistant),
a `PATCH` bump means a fix with no new capability. Each version bump gets a matching git tag
and GitHub Release.

## [Unreleased]

## [0.2.2] - 2026-08-13

### Fixed

- The 4 mypy errors that had been sitting as accepted baseline noise since before Phase 2
  are gone, not worked around:
  - `entity.py`: `coordinator.config_entry` is typed `ConfigEntry | None` on
    `DataUpdateCoordinator` generically (some coordinators run without one), but this one
    never does — added the `assert` the code already relies on implicitly.
  - `sensor.py`: `SofarSensor.native_value` was typed `-> object`, wider than
    `SensorEntity`'s own `str | int | float | date | Decimal | None`, which mypy treats as
    an invalid override. Narrowed to `str | int | float | date | None` (every field this
    reads decodes to one of those; `bool`/`IntEnum`/`IntFlag` are already `int` subtypes,
    `datetime` is already a `date` subtype — nothing here ever produces a `Decimal`).
  - `connection.py`: `build_connection`/`unit_id` took `dict[str, Any]`, but a config
    entry's own `.data` is a read-only `MappingProxyType` — not a `dict` structurally, even
    though both functions only ever read from it. Widened both to `Mapping[str, Any]`.

### Verification

- `ruff`/`mypy` — zero errors, not 4 accepted ones. All four `tests/lib/` scripts pass.

## [0.2.1] - 2026-08-13

### Fixed

- Dropped `entity_category = CONFIG` from all Phase 2 write entities (`select`/`number`/
  `switch`/`button`). Set on the assumption these were set-once settings; real usage on the
  test instance showed otherwise — they're the primary way to interact with the inverter, and
  `CONFIG` entities get tucked into a separate Configuration section below the main Controls
  section on the device page instead of showing at the top.

### Changed

- README: Status section updated with the first real-hardware findings for the write
  entities (test instance, same physical inverter as production). FeedIn Limitation
  Mode/Maximum Power confirmed via live write-and-readback; flagged as likely inert on
  installs without an external CT/meter feeding `active_power_pcc_total` (this one included —
  no fault bits set, but nothing to measure export with either). Active Power Control writes
  reach the device without error but a clean curtailment observation is still pending.
  Documented two things that caused real confusion in testing: the Update buttons commit
  whatever's staged-or-live *at the moment of the press*, not changes made afterward; and
  Active Power Control's percentage is of the inverter's rated power (`Pn`), unrelated to
  FeedIn Maximum Power despite sitting next to it in the entity list.

### Verification

- `ruff`/`mypy` clean (same 4 pre-existing unrelated errors as baseline). All four
  `tests/lib/` scripts pass.

## [0.2.0] - 2026-08-13

### Added

- Phase 2: `select`/`number`/`switch`/`button` write entities.
  - **Remote Switch On Off** (`select`) writes immediately — a plain single-register field.
  - **FeedIn: Limitation Mode** (`select`) + **FeedIn: Maximum Power** (`number`) +
    **FeedIn: Update** (`button`), and **Active Power Control** (`switch`) +
    **Active Power Control: Export Limit** (`number`) + **Active Power Control: Update**
    (`button`) — both pairs stage locally (`SofarDataUpdateCoordinator.pending`) and only
    write on the paired button press, since the device only accepts each pair as one
    combined block. Mirrors `homeassistant-solax-modbus`'s own `WRITE_DATA_LOCAL` +
    update-button shape for the same two register pairs.
  - `SofarEntity` gained a `component` parameter and now owns `available` directly (was
    duplicated per-platform in `sensor.py`; four platforms made that worth sharing).
  - Bumps the `sofar-modbus` dependency pin to `v0.1.3` — needed for its new
    `ActivePowerControl` component (`0x1105`/`0x1106`); see that project's own history for
    the register-level detail.

### Changed

- README: the writes status section no longer lists open questions — this session confirmed
  writes work on the reference hardware (live `solax_modbus` RTC-sync writes, and a
  community-confirmed `0x1105`/`0x1106` write on the same 4.4 KTLX-G3 model) and that
  `pv_power_total`'s scale factor was already correct, so both of the old blockers are gone.

### Verification

- `python3 tests/lib/test_write_entities.py` — staging vs. immediate write, paired-commit
  writes exactly one combined block, pending cleared after commit, a `ModbusError`/`ValueError`
  from a write surfaces as `HomeAssistantError` rather than a raw exception. Not yet run
  against real hardware — this integration isn't installed on the live instance yet.
- `test_smoke.py`/`test_coordinator.py`/`test_diagnostics.py` unaffected. `ruff`/`mypy` clean
  (same 4 pre-existing unrelated errors as baseline).

## [0.1.11] - 2026-08-13

### Changed

- Review feedback (Balloob): `generated_sensors.py` is gone — `SofarSensorDescription` and
  `SENSOR_DESCRIPTIONS` now live at the bottom of `sensor.py`, generated in place by
  `scripts/generate_sofar_model.py` from a `# GENERATOR: generated below` marker onward; the
  hand-written head (imports, `async_setup_entry`, `SofarSensor`) is read back from the
  existing file and preserved verbatim on every regeneration. Created a real circular import
  in the process (`sensor.py` needs `SofarConfigEntry` from `coordinator.py`; `coordinator.py`
  needed `SENSOR_DESCRIPTIONS` from `sensor.py` for its tier split) — resolved by moving that
  one import inside `_slow_tier_components()`, which only runs after both modules have
  already finished loading.
- Each generated row now only spells out a kwarg when it differs from HA's own dataclass
  default — checked directly against `homeassistant/components/sensor/__init__.py` and
  `homeassistant/helpers/entity.py` in the `core/` fork rather than assumed:
  `device_class`/`native_unit_of_measurement`/`state_class`/`entity_category`/`icon`/
  `suggested_display_precision` default to `None`, `entity_registry_enabled_default` defaults
  to `True`. Cuts a typical row from 9 lines to as few as 3.
- `probe.py` is gone. `__init__.py` no longer calls `SofarInverter.async_setup()` separately
  or wraps it in a manual `try/except` — `coordinator.async_config_entry_first_refresh()`
  already runs `async_update()` (which calls `async_setup()` internally on first use) and
  already maps any `ModbusError` to `ConfigEntryNotReady` on its own (confirmed by reading
  `DataUpdateCoordinator._async_config_entry_first_refresh()` directly in the `core/` fork,
  not assumed). Only one manual check remains afterward: `if not device.inverter_type`, for
  the unrecognized-serial case `sofar_modbus` doesn't raise for on its own.
  `SofarUnrecognizedError` moves into `config_flow.py`, the only place still needing it
  (to keep the `cannot_connect` vs `unrecognized_inverter` error-key distinction); its own
  probe switches from `async_setup()` to `async_update()` too, for the same reason
  `__init__.py`'s does — a one-time config-flow call, so the extra register reads cost
  nothing and double as validation the device actually answers.
- Relayed, not implemented: whether `sofar_modbus` itself should raise on an unrecognized
  serial instead of silently leaving `inverter_type` at zero — consistent with the same
  loud-failure-over-silent-partial-data philosophy that removed `ComponentGroup`'s old
  catch-and-continue behavior upstream (commits `115df8b`/`e7ba2dc`). `ha-sofar-modbus`
  still needs its own local check regardless of whether that lands.

### Verification

- `python3 tests/lib/test_smoke.py` — same 234-row/88-PV/173-HYBRID counts as before;
  import switched from the deleted `generated_sensors` to
  `custom_components.sofar_modbus.sensor`, same pattern `test_coordinator.py`/
  `test_diagnostics.py` already used. `test_coordinator.py`'s `slow-tier-skipped-on-off-cycles`
  case exercises `_slow_tier_components()`'s lazy import at runtime, not just mypy's static
  check. `ruff`/`mypy` clean (same 4 pre-existing unrelated errors as baseline).

## [0.1.10] - 2026-08-13

### Changed

- Migrated from `hass.data.setdefault(DOMAIN, {})[entry.entry_id]` to `entry.runtime_data`
  for storing the coordinator — the current HA config-entry-runtime-data idiom, matching
  `trovis-modbus-hass` (the reference implementation `modbus-connection`'s own docs point
  to). A new `SofarConfigEntry = ConfigEntry[SofarDataUpdateCoordinator]` type alias
  (`coordinator.py`) is threaded through `__init__.py`, `sensor.py`, and `diagnostics.py`
  in place of a bare `ConfigEntry`. `async_unload_entry` drops its `hass.data[DOMAIN].pop(...)`
  cleanup entirely — `runtime_data` is a plain attribute on the entry object, not a
  separate registry that needs clearing (confirmed against the reference's own
  `async_unload_entry`, which does nothing beyond `async_unload_platforms`).
- `entity.py` and `config_flow.py` untouched — neither reads the coordinator back via
  `hass.data`/`runtime_data`. The pre-existing mypy error on `entity.py`'s
  `coordinator.config_entry.title` access is unrelated to this (it's how HA core types
  `DataUpdateCoordinator.config_entry` as `Optional` regardless of which `ConfigEntry`
  subtype parameterizes it) and is unchanged by this migration.

### Verification

- `tests/lib/test_diagnostics.py`'s fakes updated to carry `runtime_data` directly
  instead of simulating a `hass.data` lookup. `ruff`/`mypy` clean (same 4 pre-existing
  unrelated errors as baseline, none new). All three `tests/lib/` scripts pass unchanged.

## [0.1.9] - 2026-08-13

### Added

- Config entry diagnostics (`diagnostics.py`): downloads the raw register map — every
  register the currently-served components hold, keyed by Modbus space and address —
  plus model, serial number, inverter type bitmask, and which components are served.
  Reads fresh per component rather than reusing `coordinator.data`, so the dump reflects
  live register state at download time; a component's own read failure during the
  download is recorded in `read_errors` rather than failing the whole download, matching
  how every other resilience piece in this project treats this specific flaky gateway.
  `SofarInverter` itself has no `async_read_raw()` since it stopped wrapping a
  `ComponentGroup` (0.1.7) — this reads each served component individually and merges
  the raw maps itself, the same per-component iteration `coordinator.py` already does.
  Follows `modbus-connection`'s own [integration
  guide](https://home-assistant-libs.github.io/modbus-connection/home-assistant/integration/#diagnostics).

### Verified against the reference implementation, not just the docs

- Prompted by wanting this repo to be usable as a reference itself: re-checked
  `modbus-connection`'s HA integration checklist end to end, plus fetched the official
  `developers.home-assistant.io` Modbus guide and cloned the reference implementation it
  points to (`trovis-modbus-hass`) for a real comparison, not just the docs' own
  illustrative examples.
  - **Corrected a prior claim**: entity value access here uses string-keyed
    `component`/`key` dispatch (`SofarSensorDescription`), not the docs' type-checked
    `value_fn` lambda example. Checking the reference implementation shows this isn't a
    deviation — its `TrovisSensorDescription` uses the identical `component: str` +
    `field: str` pattern, for the same reason (a large, effectively-generated attribute
    surface, not a small hand-written one). Nothing changed here; the earlier assessment
    was wrong.
  - The reference implementation also has no diagnostics download — this feature isn't
    "catching up," it's ahead of the one repo `modbus-connection`'s own docs hold up as
    the example.
  - Noted, not changed: the reference uses `entry.runtime_data = coordinator` (the
    current HA config-entry-runtime-data idiom) where this project still uses
    `hass.data.setdefault(DOMAIN, {})[entry.entry_id]` throughout `__init__.py`/
    `sensor.py`. Real difference, touches three files, and is a style migration
    unrelated to what prompted this release — left for its own decision later.

### Verification

- New `tests/lib/test_diagnostics.py`: the payload includes every served component's
  registers keyed by space/address; a component that fails mid-download is recorded in
  `read_errors` and excluded from `registers`, without affecting any other component's
  data in the same payload.

## [0.1.8] - 2026-08-13

### Added

- `coordinator.py` now gives a failed component one retry before accepting the failure,
  and splits polled components into a fast tier (read every cycle) and a slow tier —
  settings, energy counters, identity, derived from `generated_sensors.py`'s own
  `state_class` metadata rather than a separately hand-maintained list — read only every
  4th cycle (~60s at the default 15s scan interval). Prompted by comparing against
  `solax_modbus` in production, which never shows anything unavailable during the day:
  its Modbus client is constructed with `retries=1`, retrying every read once at the
  transport level before a failure is ever visible, plus a full per-register quarantine
  and background-recheck engine built around its own dynamic block re-planning.
  `modbus_connection` deliberately disables backend retries (commit `115df8b`, "the
  wrapper alone decides what happens next") and `sofar_modbus`'s `Component`/`ReadPlan`
  model has no dynamic re-blocking to bisect around a bad register, so this is scaled to
  what's actually reachable from `ha-sofar-modbus`: the retry (the practical equivalent
  of `solax_modbus`'s `retries=1`, one layer up) and the tiered cadence (fewer registers
  read per cycle, cutting exposure to the gateway's marginal timing), both entirely
  local — no `sofar_modbus`/`modbus_connection` change needed. Register-level
  bisection/quarantine stays out of scope; it would need an upstream API `sofar_modbus`
  doesn't have (excluding specific components/registers from a poll).
- A per-component `_consecutive_failures` counter, logged at `_LOGGER.debug` — no new
  diagnostic entity yet, kept minimal until there's a reason to surface it in the UI.

### Verification

- New `tests/lib/test_coordinator.py`: a component that fails once then recovers before
  the retry never appears in `UpdateReport.failed`; a failure that survives the retry is
  tracked and doesn't affect a different fast-tier component polled the same cycle; the
  existing disconnect-after-3-consecutive-timeouts recovery still fires correctly against
  the new retry-aware failure tracking; a slow-tier component is absent from both
  `updated`/`failed` on an off-cycle and present on its due cycle; a dead link
  (`ModbusConnectionError`) still raises `UpdateFailed` immediately, mid-retry included.

## [0.1.7] - 2026-08-13

### Fixed

- One slow or refused Modbus block (seen live: `GridOutput` at 0x484 timing out against the real
  inverter's gateway) no longer blanks every sensor. Bumped `sofar-modbus` to `v0.1.2`
  ([darkrain-nl/sofar-modbus@695499f](https://github.com/darkrain-nl/sofar-modbus/commit/695499f),
  three commits: `1ce1a3b`, `075016d`, `695499f`), which stopped pooling the poll into one
  `ComponentGroup` and reads each component independently instead — a component whose read fails
  keeps its previous values and is named in the returned `UpdateReport` (`updated: set[str]`,
  `failed: dict[str, ModbusError]`, keyed by the same attribute names `generated_sensors.py`
  already uses), while every other component still refreshes and notifies.
- `coordinator.py` now only raises `UpdateFailed` for `ModbusConnectionError` (a dead link) — a
  non-empty `UpdateReport.failed` is logged, not treated as a failed poll, and `coordinator.data`
  holds the report itself (the coordinator is now `DataUpdateCoordinator[UpdateReport]`, not
  `[None]`). The disconnect-after-repeated-timeouts recovery still applies, now triggered by a
  `ModbusTimeoutError` appearing in `report.failed` rather than a caught exception.
- `sensor.py`'s `SofarSensor` gained a per-entity `available` override: only the entities on a
  component that actually failed *this* poll go unavailable, checked against
  `coordinator.data.failed` — not the coordinator-wide default every other entity used to share.
- `SofarInverter.polled_components` no longer exists upstream (removed in the same three-commit
  series — there's no public "what will this device poll" surface anymore, only "what did the
  last poll attempt"). `sensor.py`'s entity-creation filter and `tests/lib/test_smoke.py` now
  derive the served set from `coordinator.data.updated | set(coordinator.data.failed)` instead —
  every component a poll attempts lands in exactly one of the two, so their union reconstructs the
  same set `polled_components` used to give, without needing the library to expose it separately.
  The smoke test's register-seeding also changed: with no pre-poll "what's served" answer
  available, it now seeds every component's fields unconditionally (an unpolled component's
  registers are simply never read, so over-seeding is harmless) rather than filtering first.

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
