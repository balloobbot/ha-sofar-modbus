# Sofar Inverter Modbus

A standalone HACS integration for **Sofar Solar** inverters, built on
[`modbus-connection`](https://github.com/home-assistant-libs/modbus-connection) instead
of a hand-rolled Modbus hub.

The register map and device model come from
[`sofar-modbus`](https://github.com/darkrain-nl/sofar-modbus) ([PyPI](https://pypi.org/project/sofar-modbus/)),
itself built on `modbus-connection` and tracing the Sofar register map back to the Sofar plugin of
[`homeassistant-solax-modbus`](https://github.com/wills106/homeassistant-solax-modbus).
This repo also extracts its own HA-facing sensor metadata (names, device classes, icons)
directly from that plugin's source — see [The register map is
generated](#the-register-map-is-generated) — which is why its licence (Apache-2.0) is
copied into [`LICENSE`](LICENSE) alongside this project's own.

## Status

**Read-only sensors are live.** Verified live against one PV-only inverter (`SS2E...`,
4.4 KTLX-G3, `PV | X3 | GEN`) — 88 entities, correct scaling, stable polling under a
48-register block cap the hardware needs.

The live gateway is intermittently slow on some blocks — a real, observed condition, not a
bug — and the integration now absorbs that instead of surfacing it: a component whose read
fails gets one retry before it's ever recorded as failed, and only the entities on a
component that's still failing after that go `unavailable` — not the other 87. See
[Resilience](#resilience) below.

**Write entities are built and have been exercised against the real inverter** — not on the
main live instance (see the `tmodbus` pin conflict below), but on a separate test instance
pointed at the same physical hardware over the network. What's built, and what testing found:

- **Remote Switch On Off** (`select`) — a plain single-register write, applied immediately.
  Not yet toggled in testing (it's plausibly a remote shutdown of the inverter's grid-tie —
  left alone on a live producing inverter).
- **FeedIn: Limitation Mode** (`select`) + **FeedIn: Maximum Power** (`number`) +
  **FeedIn: Update** (`button`) — the device only accepts mode and power as one combined
  write, so the select/number stage a value locally and the button commits both together.
  **Confirmed working**: set to "Enabled - 3-phase limit" / 1000 W, and the device read the
  new mode and power back on the next poll. **Likely inert on installs without an external
  CT/meter wired to the inverter**, this one included — the register this reads/limits
  against (`active_power_pcc_total`) only reflects real export with a meter feeding it (the
  register map has dedicated meter-communication-failure fault codes), so without one the
  write succeeds but has nothing to act on.
- **Active Power Control** (`switch`) + **Active Power Control: Export Limit** (`number`) +
  **Active Power Control: Update** (`button`) — same staged-then-commit shape, for
  `sofar-modbus`'s write path (register `0x1105`/`0x1106`). Writes reach the device
  without error. Unlike FeedIn Limitation, this caps the inverter's own output directly and needs no
  external meter, so it should work on any install. **The percentage is of the inverter's
  rated power** (`Pn` — 4.4 kW for this model), unrelated to FeedIn Maximum Power despite
  sitting right next to it in the entity list: 50% here means ~2.2 kW, not 50% of whatever
  the FeedIn number is set to.

**The staged/commit entities have an ordering trap**: the Update button commits whatever the
select/number/switch currently show *at the moment you press it* — staged or, if untouched,
last-read-from-device — not anything changed afterward. Set the switch and/or number first,
then press Update; pressing Update first and adjusting the inputs afterward silently
re-writes the old values instead.

This mirrors the exact UX `homeassistant-solax-modbus`'s own `plugin_sofar.py` uses for the
same two register pairs (`WRITE_DATA_LOCAL` + a paired update button), not a new design.

The three things that used to be open questions before starting this are resolved:

1. **This inverter does accept Modbus writes.** The production `homeassistant-solax-modbus`
   install on this same hardware runs a weekly `button.sofar_sync_rtc` press (a genuine
   7-register block write) with a clean history and a 100% communication success rate. A
   SOFAR 4.4KTLX-G3 owner — this exact model — also confirmed `0x1105`/`0x1106` (Active Power
   Control) working live: real inverter output visibly dropped from 3.4kW to 0.8kW at a 30%
   limit ([wills106/homeassistant-solax-modbus#2107](https://github.com/wills106/homeassistant-solax-modbus/issues/2107)).
   SofarSolar's own Modbus User Guide documents no unlock code, protocol toggle, or "remote
   control enable" register for this inverter family — write access is available as soon as
   RS485 address/baud are set, which they already are.
2. ~~A firmware update with Modbus/SunSpec fixes may be relevant~~ — nothing found tying write
   capability to firmware version for the G3 family; only the PV-scale bug below was
   version-dependent, and that's understood regardless of version now.
3. `pv_power_total`'s scale factor is resolved upstream:
   [wills106/homeassistant-solax-modbus#2032](https://github.com/wills106/homeassistant-solax-modbus/pull/2032)
   confirms "Sofar KTLX-G3 uses same scaling as Hybrid inverters" (`0.1`, not `0.01`) —
   `sofar-modbus`'s `pv_power_total` already uses `0.1`, so no code change was needed here.

HYBRID-only features — battery-pack telemetry, passive mode, EPS, TOU — are generated from
the same register map but **have not been tested against real hardware** and won't be until
a HYBRID Sofar inverter is available. If you have one and something misbehaves, please open
an issue with your serial number prefix and a [diagnostics download](#resilience).

**Phase 4 write controls (Charger Use Mode, EPS Mode, Passive Mode) are built and pass
against a synthetic HYBRID identity (`modbus_connection.mock`) — the same tooling and depth
of testing the three Phase 2 controls had before real hardware existed to try them on — but
have not been exercised against a real HYBRID inverter.** What's built:

- **Charger Use Mode** (`select`) — a plain single-register write, applied immediately, same
  shape as Remote Switch On Off.
- **EPS Mode** (`select`) — applied immediately; the device wants a reserved wait-time
  register alongside it, which the library always writes as `0`. Only appears if the
  **Read EPS registers** setup option is enabled — off by default, since the library (and
  the device) refuse this block on an inverter that isn't wired for EPS.
- **Passive: Timeout** (`number`) + **Passive: Timeout Action** (`select`) + **Passive:
  Timeout Update** (`button`), and **Passive: Desired Grid Power** + **Passive: Minimum/
  Maximum Battery Power** (`number` ×3) + **Passive: Power Update** (`button`) — two
  independent staged groups, same shape as FeedIn Limitation and Active Power Control.

None of this can appear on a PV-only inverter (this project's own reference hardware
included) — every entity above is gated behind the component the underlying register block
belongs to, which a PV-only `inverter_type` never serves.

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
   reconnection, and typed exceptions. A standard PyPI dependency (`modbus-connection[tmodbus]>=4.7.0,<5.0.0`
   in `pyproject.toml`/`manifest.json`).
2. **[`sofar-modbus`](https://github.com/darkrain-nl/sofar-modbus)** — standard PyPI dependency
   (`sofar-modbus>=0.1.5,<0.2.0`). The Sofar register map as typed `Component` classes, plus
   `SofarInverter`/`SofarLegacyInverter` device objects. HA-free, tested independently of
   this repo. It reads each polled component independently and reports what happened via
   an `UpdateReport` (`updated: set[str]`, `failed: dict[str, ModbusError]`) rather than
   failing the whole poll when one component's block is slow or refused — see
   [Resilience](#resilience) for how this integration builds on that.
3. **The integration** (`custom_components/sofar_modbus/`) — owns the `ModbusConnection`,
   runs `SofarDataUpdateCoordinator`, exposes entities, bundles local brand assets, and serves a
   [diagnostics download](#resilience).

### The register map is generated

The sensor description metadata in `custom_components/sofar_modbus/sensor.py` (below the
`# GENERATOR: generated below` marker) is produced by
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
uv run python scripts/extract_sofar_ast.py       # sanity-check counts against upstream
uv run python scripts/generate_sofar_model.py
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

- **One retry before a failure counts.** `SofarDataUpdateCoordinator` gives a component that
  failed a second, immediate try before recording it in the poll's `UpdateReport.failed`.
  On total outages (where zero components responded), retries are skipped to avoid doubling timeout latency.
- **Transition-only logging.** Component read failures emit a `WARNING` only on the initial transition
  into failure to prevent log spam across polling cycles, and clear automatically on recovery.
- **Tiered scan cadence.** After the first poll (which reads everything, to learn what's
  served), later polls split components into a fast tier — telemetry measurements (grid, PV, state) — read every
  cycle (default 15s), and a slow tier — settings, write controls, energy counters, identity — read every
  4th cycle (~60s). Write entities automatically force an immediate slow-tier refresh upon committing.
- **Total sensor preservation & restart restoration.** Cumulative energy sensors (`TOTAL` and `TOTAL_INCREASING`)
  stay `available = True` through link drops and nighttime shutdown to protect Energy Dashboard statistics.
  `SofarTotalSensor` uses `RestoreSensor` to restore the last known value across Home Assistant restarts and
  seeds the torn-read dip guard high-water mark immediately from the first poll.
- **Connection recovery.** Repeated timeouts on an unresponsive link automatically trigger `connection.disconnect()`
  to reset the transport.
- **Diagnostics download** (Settings → Devices & Services → this integration → device →
  Download diagnostics) uses `SofarInverter.async_read_raw()` to dump raw register values for every served
  component without crashing if a component fails.

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

Dependencies are managed with [`uv`](https://github.com/astral-sh/uv):

```bash
uv sync --group test --group dev
uv run python tests/lib/test_smoke.py          # probe -> device -> entity-filter, mock backend
uv run python tests/lib/test_coordinator.py    # retry, tiered cadence, disconnect recovery
uv run python tests/lib/test_diagnostics.py    # diagnostics payload, mock backend
uv run python tests/lib/test_write_entities.py # stage/commit writes, mock backend
uv run ruff check .
uv run mypy custom_components/sofar_modbus
```

## Versioning

[`CHANGELOG.md`](CHANGELOG.md) tracks every release, [Keep a Changelog](https://keepachangelog.com/)
format. This project follows [Semantic Versioning](https://semver.org/): while the major version
is `0`, a `MINOR` bump means new user-facing capability (a new platform, new entities reachable
from Home Assistant); a `PATCH` bump means a fix with no new capability. Every version bump in
`manifest.json` gets a matching git tag and [GitHub Release](https://github.com/darkrain-nl/ha-sofar-modbus/releases).

## Roadmap

- **Phase 0/1 — done.** Read-only sensors on `modbus-connection`.
- **Phase 3 — done (`0.1.7`–`0.1.9`, `0.3.5`).** Retry-before-fail, transition-only warning logging, tiered scan cadence, write-trigger refresh, diagnostics download — see [Resilience](#resilience).
- **`entry.runtime_data` idiom migration — done (`0.1.10`).**
- **Phase 2 — done (`0.2.0`).** `select`/`number`/`switch`/`button` write entities for Remote Switch,
  FeedIn Limitation, and Active Power Control.
- **Phase 4 — code-complete, mock-verified (`0.3.0`).** Charger Use Mode, EPS Mode and
  Passive Mode write entities — see [Status](#status).
- **Brand Assets — done (`0.3.6`).** Local icons and logos in `custom_components/sofar_modbus/brand/`.
- **Phase 5 — not started.** Energy dashboard device.
- **Not started.** Serial (RTU) transport, delegating to Home Assistant's built-in Modbus hub.
