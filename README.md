# Sofar Inverter Modbus

A standalone HACS integration for **Sofar Solar** inverters, built on
[`modbus-connection`](https://github.com/home-assistant-libs/modbus-connection) instead
of a hand-rolled Modbus hub.

The register map and device model come from
[`sofar-modbus`](https://github.com/darkrain-nl/sofar-modbus) — a fork of
[`balloobbot/sofar-modbus`](https://github.com/balloobbot/sofar-modbus) (Apache-2.0),
itself built on `modbus-connection` and, like this integration, tracing the Sofar
register map back to the Sofar plugin of
[`homeassistant-solax-modbus`](https://github.com/wills106/homeassistant-solax-modbus).
This repo also extracts its own HA-facing sensor metadata (names, device classes, icons)
directly from that plugin's source — see [The register map is
generated](#the-register-map-is-generated) — which is why its licence (Apache-2.0) is
copied into [`LICENSE`](LICENSE) alongside this project's own.

## Status

**Early / read-only.** Sensors work and have been verified live against one PV-only inverter
(`SS2E...`, 4.4 KTLX-G3, `PV | X3 | GEN`) — 88 entities, correct scaling, stable polling under
a 48-register block cap the hardware needs.

The live gateway is intermittently slow on some blocks — a real, observed condition, not a
bug — and the integration now absorbs that instead of surfacing it: a component whose read
fails gets one retry before it's ever recorded as failed, and only the entities on a
component that's still failing after that go `unavailable` — not the other 87. See
[Resilience](#resilience) below.

**Writable entities (numbers, selects, buttons) are not built yet — paused deliberately.**
The `sofar-modbus` library already exposes `writable=True` fields and `async_write_*`
convenience methods for most of the settings registers (feed-in limit, EPS control,
passive-mode setpoints, RTC, IV-curve-scan), but **no write UI is exposed** — nothing can
be triggered from Home Assistant yet. Writes are being held back until:

1. **Whether this inverter's Modbus interface accepts writes at all is unconfirmed.** Writes
   never worked via `homeassistant-solax-modbus` on this hardware either, and that may be
   this inverter specifically (remote-write not enabled in its own menu, or similar) rather
   than anything integration-side.
2. **A firmware update with Modbus/SunSpec fixes may be relevant** and hasn't been installed
   yet — worth doing before spending time debugging writes against firmware that's already
   known to need an update. This is the current blocker.
3. `pv_power_total`'s scale factor (0.1 vs 0.01) needs a daylight check against real PV
   output before treating any of the current numeric decoding as fully trusted — see the
   2024 upstream issue [wills106/homeassistant-solax-modbus#784](https://github.com/wills106/homeassistant-solax-modbus/issues/784),
   opened by this repo's author, still unresolved there.

HYBRID-only features — battery-pack telemetry, passive mode, EPS, TOU — are generated from
the same register map but **have not been tested against real hardware** and won't be until
a HYBRID Sofar inverter is available. If you have one and something misbehaves, please open
an issue with your serial number prefix and a [diagnostics download](#resilience).

Only Modbus TCP is supported so far. Serial (RTU) and delegating to Home Assistant's
built-in Modbus hub are planned but not implemented.

**Do not run this alongside `homeassistant-solax-modbus` on the same Home Assistant
instance.** That integration pins `tmodbus==0.4.1` exactly in its own `manifest.json`, and
Home Assistant re-processes that pin on every restart while the integration is loaded —
forcing tmodbus back down to `0.4.1` even if something else needs newer. `modbus-connection`
needs `tmodbus>=0.5.1`, so `modbus_connection.tmodbus` fails to import
(`cannot import name 'create_async_udp_client' from 'tmodbus'`) as long as both are
installed. Test this integration on a separate instance without `solax_modbus` loaded.

## Architecture

Three layers, per `modbus-connection`'s own
[integration guide](https://home-assistant-libs.github.io/modbus-connection/home-assistant/integration/):

1. **`modbus-connection`** — the connection, block-read planning, decoding,
   reconnection, and typed exceptions. A normal dependency (`modbus-connection[tmodbus]`
   in `pyproject.toml`/`manifest.json`).
2. **[`sofar-modbus`](https://github.com/darkrain-nl/sofar-modbus)** — also a normal
   dependency (pinned via `git+https`, not vendored source), not a PyPI package yet. The
   Sofar register map as typed `Component` classes, plus `SofarInverter`/
   `SofarLegacyInverter`, the top-level device objects. HA-free, tested independently of
   this repo. It reads each polled component independently and reports what happened via
   an `UpdateReport` (`updated: set[str]`, `failed: dict[str, ModbusError]`) rather than
   failing the whole poll when one component's block is slow or refused — see
   [Resilience](#resilience) for how this integration builds on that.
3. **The integration** (`custom_components/sofar_modbus/`) — owns the `ModbusConnection`,
   runs `SofarDataUpdateCoordinator`, exposes entities, and serves a
   [diagnostics download](#resilience).

### The register map is generated

`custom_components/sofar_modbus/generated_sensors.py` is produced by
[`scripts/generate_sofar_model.py`](scripts/generate_sofar_model.py), which walks the
upstream `plugin_sofar.py` with Python's `ast` module (no `homeassistant` import needed,
via [`extract_sofar_ast.py`](scripts/extract_sofar_ast.py)) to pull each entity's HA-facing
metadata — name, device class, unit, icon, category — and introspects the *installed*
`sofar-modbus` library (`sofar_modbus.model.SofarComponentBase`) to work out which of its
attributes (`grid`, `pv_1_2`, `energy`, …) serves each field. It no longer generates the
register/decode layer itself — that's `sofar-modbus`'s job now. Output is **checked in**;
the generator does not run at integration runtime. Re-run it after pulling an updated
`plugin_sofar.py` or a new `sofar-modbus` version:

```bash
python3 scripts/extract_sofar_ast.py       # sanity-check counts against upstream
python3 scripts/generate_sofar_model.py
```

The upstream commit each generation ran against is recorded in the generated file's header.

### Which fields a given inverter reads

Every field carries an `allowedtypes` bitmask (ported from the upstream plugin's
`GEN`/`X1`/`X3`/`PV`/`HYBRID`/`EPS`/... flags) inside `sofar-modbus` itself — `SofarInverter`
probes the serial number at setup, classifies the model, and settles which components apply,
privately (there's no public "what will this device poll" property). This integration learns
the served set the same way it learns anything else about a poll: `UpdateReport.updated |
set(UpdateReport.failed)` — every component a poll attempts lands in exactly one of the two,
so their union is the served set. `sensor.py` and `diagnostics.py` both use this to decide
what to expose.

### Resilience

Two things `homeassistant-solax-modbus` gets from a transport-level `retries=1` and a full
per-register quarantine/background-recheck engine, scaled down to what's actually reachable
from this stack (`modbus-connection` deliberately disables backend retries so the caller
decides what happens next, and `sofar-modbus`'s fixed, cached `Component` layout has no
dynamic re-blocking to bisect a bad register out of — register-level quarantine would need
an upstream API that doesn't exist):

- **One retry before a failure counts.** `SofarDataUpdateCoordinator` gives a component that
  failed a second, immediate try before recording it in the poll's `UpdateReport.failed`.
- **Tiered scan cadence.** After the first poll (which reads everything, to learn what's
  served), later polls split components into a fast tier — grid, PV, state — read every
  cycle, and a slow tier — settings, energy counters, identity, derived from
  `generated_sensors.py`'s own `state_class` metadata — read only every 4th cycle (~60s at
  the default 15s interval).
- A link that's up but unresponsive (a wedged serial-to-network bridge) still triggers
  `connection.disconnect()` after repeated timeouts, same as before.
- **Diagnostics download** (Settings → Devices & Services → this integration → device →
  Download diagnostics) dumps the raw register map for every currently-served component,
  read fresh at download time, for an issue report showing exactly what the device answered.

## Installing (HACS custom repository)

1. HACS → Integrations → ⋮ → Custom repositories → add this repo's URL, category
   "Integration".
2. Install "Sofar Inverter Modbus", restart Home Assistant.
3. Settings → Devices & Services → Add Integration → "Sofar Inverter Modbus" → enter the
   inverter's IP and Modbus TCP port (usually 502).

**It cannot run side by side with `homeassistant-solax-modbus` on the same Home Assistant
instance** — see the `tmodbus` version-pin conflict above. Verify it on a separate instance
first (a HACS install can point at the same inverter over the network without touching your
existing `solax_modbus` setup at all), and only install it on your main instance once you're
ready to remove `solax_modbus` there.

## Development

Dependencies are [PEP 735](https://peps.python.org/pep-0735/) groups, not
`[project.optional-dependencies]` extras — install with `--group`, not `.[test]`:

```bash
uv venv && source .venv/bin/activate
uv pip install -e . --group test --group dev
python3 tests/lib/test_smoke.py         # probe -> device -> entity-filter, mock backend
python3 tests/lib/test_coordinator.py   # retry, tiered cadence, disconnect recovery
python3 tests/lib/test_diagnostics.py   # diagnostics payload, mock backend
ruff check .
mypy custom_components/sofar_modbus
```

## Versioning

[`CHANGELOG.md`](CHANGELOG.md) tracks every release, [Keep a Changelog](https://keepachangelog.com/)
format. This project follows [Semantic Versioning](https://semver.org/): while the major version
is `0`, a `MINOR` bump means new user-facing capability (a new platform, new entities reachable
from Home Assistant); a `PATCH` bump means a fix with no new capability. Every version bump in
`manifest.json` gets a matching git tag and [GitHub Release](https://github.com/darkrain-nl/ha-sofar-modbus/releases).

## Roadmap

- **Phase 0/1 — done.** Read-only sensors on `modbus-connection`.
- **Phase 3 — done (`0.1.7`–`0.1.9`).** Retry-before-fail, tiered scan cadence, diagnostics
  download — see [Resilience](#resilience). Register-level quarantine/bisection, the part
  of `solax_modbus`'s engine this doesn't attempt, stays out of scope (see that section for
  why).
- **`entry.runtime_data` idiom migration — done (`0.1.10`).**
- **Phase 2 — next, on hold.** Number/select/button write entities. `sofar-modbus` already
  has the writable fields and `async_write_*` helpers; blocked on the inverter-side firmware
  update noted in [Status](#status), not on anything integration-side.
- **Phase 4 — not started.** HYBRID hardware verification (no HYBRID Sofar inverter
  available to test against).
- **Phase 5 — not started.** Energy dashboard device.
- **Not started.** Serial (RTU) transport, delegating to Home Assistant's built-in Modbus
  hub.
