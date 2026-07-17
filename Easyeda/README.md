# ProGenEDA EasyEDA Pro Backend

This package generates one native EasyEDA Pro `.eprj` SQLite project from the
same canonical circuit JSON used by the other ProGenEDA backends. It is
independent from `kicad/` at runtime.

The backend is donor-native. Every symbol, device, footprint, pad, power
symbol, and net-port payload is copied unchanged from the authorized EasyEDA
source records. The portable executable embeds a compact locked bundle
containing only the audited rows needed by the supported catalogue, not the
desktop application or complete standard library. The generator creates
project rows, component instances, coordinates, references, values, net
bindings, wires, tracks, vias, and the board outline.

## Quick Start

```bash
python -m Easyeda.executable run \
  Easyeda/examples/regulated_5v_supply.json \
  --output-root /tmp/progen_easyeda_runs
```

An authorized source installation may still be supplied with `--source-pack`
as a development-time override.

The primary output is `<project-name>.eprj`. Each run also creates an internal
ZIP with the normalized input, placement, routing, donor provenance, PCB
decision, all attempted PCB routing variations, and validation reports.

Useful deterministic commands:

```bash
# Report and repair common JSON mistakes without generating.
Easyeda/dist/progen-easyeda validate-input circuit.json
Easyeda/dist/progen-easyeda fix-input circuit.json --output fixed.json

# List fields exposed by the normal value/reference editor.
Easyeda/dist/progen-easyeda editable circuit.json

# Apply validated value/reference edits to canonical JSON.
Easyeda/dist/progen-easyeda edit circuit.json edits.json --output edited.json

# Stream truthful completed pipeline stages for a website/worker adapter.
Easyeda/dist/progen-easyeda run circuit.json --output-root runs --events ndjson
```

## Release Contract

- 59 locked logical catalogue entries backed by 57 physical donor families
  plus native `GND` and `VCC` terminal families.
- At most 80 input component instances.
- Deterministic tolerant input repair before generation. Missing donor pins are
  explicitly completed as terminalized `GUESS_*` nets and reported; clean
  canonical inputs pass with zero changes and zero guesses.
- `wire`, `terminal`, and `combination` schematic modes.
- `combination` is the default.
- In combination mode, each power/ground net is physically routed to one
  shared native named terminal. High-fanout non-power nets above five use
  endpoint net ports.
- Failed schematic wire routes fall back to native net ports in combination
  mode, never to hidden labels.
- Different nets may cross at a point, but may not share any positive-length
  horizontal or vertical wire span. Planning, terminal placement, and the
  independent native-record validator all enforce this readability rule.
- Routing lanes remain local to each branch, use compact four-unit spacing,
  and have a bounded detour and emitted-wire envelope. A difficult net is
  terminalized in combination mode instead of producing a whole-sheet loop.
- Single-endpoint guessed nets may attach a source-native net port directly at
  the component pin; they remain explicit and auditable without decorative
  wire stubs.
- Basic PCB output is included in the same `.eprj` when all used source devices
  have verified footprint/pad mappings and the two-layer router succeeds.
- The hardened PCB profile supports at most 32 physical components. `GND` and
  `VCC` schematic terminals do not count as physical PCB components.
- PCB failure never invalidates a correct schematic. The project is emitted
  without a PCB document and `pcb_report.json` explains why.
- Static validation does not replace EasyEDA acceptance. A release candidate
  must also open in installed EasyEDA Pro through the `.eprj` file association.
  The acceptance helper opens a disposable copy and proves the audited artifact
  was not rewritten.
- Generated projects carry an explicit EasyEDA 3.x branch identity and contain
  no stale donor history or copper-cache rows. This avoids the desktop
  application's legacy "Failed to get historical project data" conversion.
- The authorized offline EasyEDA Pro build requires
  `~/Documents/EasyEDA-Pro/lceda-pro-activation.txt` before native `.eprj`
  projects can reach the editor. The installer fixes NixOS compatibility but
  does not create, alter, or bypass that activation. On NixOS it resolves a
  complete donor-compatible dynamic-library path and patches both the Electron
  executable and its crash reporter without changing the system installation.

See [INPUT_JSON.md](INPUT_JSON.md), [SUPPORTED_COMPONENTS.md](SUPPORTED_COMPONENTS.md),
[ARCHITECTURE.md](ARCHITECTURE.md), and the
[300-case qualification record](qualification/README.md).

The shipping website handoff is
[`release/newwebsite-easyeda-handoff-2026_07_17.zip`](release/newwebsite-easyeda-handoff-2026_07_17.zip).
It contains the portable, all 300 named circuit inputs, the complete website
overlay, guarded installer, registry/UI payloads, tests, and release evidence.
