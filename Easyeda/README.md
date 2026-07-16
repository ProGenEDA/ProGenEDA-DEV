# ProGenEDA EasyEDA Pro Backend

This package generates one native EasyEDA Pro `.eprj` SQLite project from the
same canonical circuit JSON used by the other ProGenEDA backends. It is
independent from `kicad/` at runtime.

The backend is donor-native. Every symbol, device, footprint, pad, power
symbol, and net-port payload is copied unchanged from an authorized EasyEDA Pro
source package supplied at generation time. The generator only creates project
rows, component instances, coordinates, references, values, net bindings,
wires, tracks, vias, and the board outline.

## Quick Start

```bash
python -m Easyeda.executable run \
  Easyeda/examples/regulated_5v_supply.json \
  --source-pack /home/zaruka/.local/opt/easyeda-pro \
  --output-root /tmp/progen_easyeda_runs
```

The primary output is `<project-name>.eprj`. Each run also creates an internal
ZIP with the normalized input, placement, routing, donor provenance, PCB
decision, and validation report.

## Release Contract

- Exactly 40 locked logical component families.
- At most 80 input component instances.
- `wire`, `terminal`, and `combination` schematic modes.
- `combination` is the default.
- In combination mode, each power/ground net is physically routed to one
  shared native named terminal. High-fanout non-power nets above five use
  endpoint net ports.
- Failed schematic wire routes fall back to native net ports in combination
  mode, never to hidden labels.
- Basic PCB output is included in the same `.eprj` when all used source devices
  have verified footprint/pad mappings and the two-layer router succeeds.
- PCB failure never invalidates a correct schematic. The project is emitted
  without a PCB document and `pcb_report.json` explains why.
- Static validation does not replace EasyEDA acceptance. A release candidate
  must also open in installed EasyEDA Pro through the `.eprj` file association.
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
and [ARCHITECTURE.md](ARCHITECTURE.md).
