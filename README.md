# Sofar Inverter Modbus

A standalone HACS integration for **Sofar Solar** inverters, built on
[`modbus-connection`](https://github.com/home-assistant-libs/modbus-connection) instead
of a hand-rolled Modbus hub.

This is a from-scratch integration extracted from the Sofar plugin of
[`homeassistant-solax-modbus`](https://github.com/wills106/homsassistant-solax-modbus) — only
Sofar, restructured onto `modbus-connection`'s connection + typed device-modelling layers so
it stays a viable candidate for Home Assistant Core later. See that project's licence
(Apache-2.0, copied into [`LICENSE`](LICENSE)) for the register-map provenance.

## Status

**Early / read-only.** Sensors work and have been verified live against one PV-only inverter
(`SS2E...`, 4.4 KTLX-G3, `PV | X3 | GEN`) — 88 entities, correct scaling, stable polling under
a 48-register block cap the hardware needs (see `CHANGELOG.md` for what live testing caught
and fixed: entity filtering, a silently-dropped scale factor, and this block-size limit).

**Writable entities (numbers, selects, buttons) are not built yet — paused deliberately.**
Three settings registers (`parallel_address`, `remote_switch_on_off`, `charger_use_mode`) are
marked `writable=True` at the library level as groundwork, but **no write UI is exposed** —
nothing can be triggered from Home Assistant yet. Writes are being held back until:

1. **Whether this inverter's Modbus interface accepts writes at all is unconfirmed.** Writes
   never worked via `homeassistant-solax-modbus` on this hardware either, and that may be
   this inverter specifically (remote-write not enabled in its own menu, or similar) rather
   than anything integration-side.
2. **A firmware update with Modbus/SunSpec fixes may be relevant** and hasn't been installed
   yet — worth doing before spending time debugging writes against firmware that's already
   known to need an update.
3. `pv_power_total`'s scale factor (0.1 vs 0.01) needs a daylight check against real PV
   output before treating any of the current numeric decoding as fully trusted — see the
   2024 upstream issue [wills106/homeassistant-solax-modbus#784](https://github.com/wills106/homeassistant-solax-modbus/issues/784),
   opened by this repo's author, still unresolved there.

HYBRID-only features — battery-pack telemetry, passive mode, EPS, TOU — are generated from
the same register map but **have not been tested against real hardware** and won't be until
a HYBRID Sofar inverter is available. If you have one and something misbehaves, please open
an issue with your serial number prefix and a diagnostics download.

Only Modbus TCP is supported so far. Serial (RTU) and delegating to Home Assistant's
built-in Modbus hub are planned but not implemented.

**Do not run this alongside `homeassistant-solax-modbus` on the same Home Assistant
instance.** That integration pins `tmodbus==0.4.1` exactly in its own `manifest.json`, and
Home Assistant re-processes that pin on every restart while the integration is loaded —
forcing tmodbus back down to `0.4.1` even if something else needs newer. `modbus-connection`
needs `tmodbus>=0.5.1`, so `modbus_connection.tmodbus` fails to import
(`cannot import name 'create_async_udp_client' from 'tmodbus'`) as long as both are
installed. Test this integration on a separate instance without `solax_modbus` loaded — see
`CHANGELOG.md` in the workspace root for how this was diagnosed.

## Architecture

Three layers, per `modbus-connection`'s own
[integration guide](https://home-assistant-libs.github.io/modbus-connection/home-assistant/integration/):

1. **`modbus-connection`** (PyPI dependency) — the connection, block-read planning,
   decoding, reconnection, and typed exceptions.
2. **`custom_components/sofar_modbus/sofar/`** — a vendored, **HA-free** device library:
   the Sofar register map as typed `Component` classes, plus `SofarInverter`, the top-level
   device object. It never imports `homeassistant` — enforced by
   `tests/lib/test_no_ha_imports.py` — so it is mechanically extractable to its own PyPI
   package if this integration is ever proposed for Core.
3. **The integration** (everything else under `custom_components/sofar_modbus/`) — owns the
   `ModbusConnection`, runs a `DataUpdateCoordinator`, and exposes entities.

### The register map is generated

`custom_components/sofar_modbus/sofar/components/*.py`,
`custom_components/sofar_modbus/sofar/const.py` (bitmasks, per-field allowedtypes, the
serial-prefix → model table) and `custom_components/sofar_modbus/generated_sensors.py` are
produced by [`scripts/generate_sofar_model.py`](scripts/generate_sofar_model.py), which walks
the upstream `plugin_sofar.py` with Python's `ast` module (no `homeassistant` import needed)
and translates each entity description into `modbus_connection.model` field helpers. Output
is **checked in**; the generator does not run at integration runtime. Re-run it after pulling
an updated `plugin_sofar.py`:

```bash
python3 scripts/extract_sofar_ast.py       # sanity-check counts against upstream
python3 scripts/generate_sofar_model.py
```

The upstream commit each generation ran against is recorded in the generated files' headers.

### Which fields a given inverter reads

Every field carries an `allowedtypes` bitmask (ported from the upstream plugin's
`GEN`/`X1`/`X3`/`PV`/`HYBRID`/`EPS`/... flags). At setup, `SofarInverter` probes the serial
number, classifies the model, and calls `Component.restrict_fields()` to narrow each
`Component` to only the registers that model actually serves — this is what stops one
unserved register from failing an entire block read on a device that doesn't implement it.
See [`sofar/device.py`](custom_components/sofar_modbus/sofar/device.py).

## Installing (HACS custom repository)

1. HACS → Integrations → ⋮ → Custom repositories → add this repo's URL, category
   "Integration".
2. Install "Sofar Inverter Modbus", restart Home Assistant.
3. Settings → Devices & Services → Add Integration → "Sofar Inverter Modbus" → enter the
   inverter's IP and Modbus TCP port (usually 502).

It can run **side by side** with `homeassistant-solax-modbus` — the entity IDs don't
collide — which is the recommended way to verify it against your existing setup before
removing the old integration.

## Development

```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[test]"
python3 tests/lib/test_smoke.py   # probe -> device -> entity-filter smoke test, mock backend
```

## Roadmap

See the project plan for the phased build-out (writes, quarantine/health, serial + Core-hub
transports, HYBRID verification, energy dashboard, cutover from `solax_modbus`).
