# ProGenEDA EasyEDA Pro Backend

This independent backend compiles canonical circuit JSON into one native
EasyEDA Pro `.eprj` SQLite project. It does not import from `kicad/` at
runtime.

The backend is donor-native: symbols, devices, footprints, pads, power
terminals, and net-port payloads are resolved from audited EasyEDA source
records. The portable generator contains only the compact locked record bundle
needed by the supported catalogue. It does not package the EasyEDA desktop
application or its complete library.

## What It Produces

For a supported request, the pipeline emits:

- one editable native `<project-name>.eprj` project;
- a schematic using source-resolved components, wires, terminals, and net
  ports according to the chosen routing mode;
- a bounded two-layer PCB in the same project when all used devices have exact
  footprint/pad mappings and physical validation passes; and
- an internal ZIP containing normalized input, fixer report, placement,
  routing, donor provenance, PCB decisions and variants, and validation
  reports.

The primary user artifact is the `.eprj` project. Internal records are kept for
audit and regeneration rather than mixed into the user-facing project folder.

## Run The Portable Executable

```bash
Easyeda/dist/progen-easyeda run INPUT.json \
  --output-root /tmp/progen-easyeda-runs \
  --routing-mode combination \
  --events ndjson
```

The portable executable is the normal distribution artifact. It can generate
and run deterministic validation without an installed EasyEDA application.

## Run From Source

```bash
PYTHONPATH=. python -m Easyeda.executable run \
  Easyeda/examples/regulated_5v_supply.json \
  --output-root /tmp/progen-easyeda-runs \
  --routing-mode combination
```

An authorized source installation can be supplied with `--source-pack` as a
development-time override.

Useful deterministic commands:

```bash
# Report and repair common input problems without generating a project.
Easyeda/dist/progen-easyeda validate-input circuit.json
Easyeda/dist/progen-easyeda fix-input circuit.json --output fixed.json

# Discover fields exposed by the normal reference/value editor.
Easyeda/dist/progen-easyeda editable circuit.json

# Apply validated JSON edits and emit normalized JSON.
Easyeda/dist/progen-easyeda edit circuit.json edits.json --output edited.json

# Stream completed pipeline stages for a worker or website adapter.
Easyeda/dist/progen-easyeda run circuit.json --output-root runs --events ndjson
```

## Routing And PCB Contract

- The locked catalogue contains 59 logical entries backed by 57 physical donor
  families, plus native `GND` and `VCC` terminal families.
- A schematic request may contain at most 80 component instances.
- `wire`, `terminal`, and `combination` modes are supported; `combination` is
  the default.
- Combination mode uses explicit native terminals for power/ground, selected
  high-fanout nets, and failed wire routes. Strict wire mode fails rather than
  silently terminalizing a net.
- Distinct nets may cross at a point but may not share a positive-length wire
  span. The planner and native validator enforce this readability constraint.
- PCB output is bounded to 32 physical components. `GND` and `VCC` schematic
  terminals do not count as physical PCB components.
- A PCB failure never invalidates an otherwise valid schematic. The project is
  emitted without a board document and the PCB report records the reason.

## Validation And Acceptance

The native validator checks source-record hashes, components, pins, expected
nets, geometry, wire-span overlap, footprint/pad mapping, and board-level
connectivity. Input repair is deterministic: a guessed or completed net is
named `GUESS_*`, terminalized, and reported. A clean canonical input produces
zero guesses and zero repairs.

Static validation is necessary but not desktop acceptance. Release evidence
also opens a disposable copy of each selected project through the installed
EasyEDA Pro file association and confirms that the audited original was not
rewritten. Generated projects carry a native EasyEDA 3.x identity and omit
legacy history/cache rows that trigger conversion failures.

## Evidence And Documentation

- [Input JSON contract](INPUT_JSON.md)
- [Supported components](SUPPORTED_COMPONENTS.md)
- [Architecture](ARCHITECTURE.md)
- [300-circuit qualification](qualification/README.md)
- [Qualification results](qualification/RESULTS_2026_07_17.md)
- [Website handoff](release/newwebsite_easyeda_handoff_2026_07_17/README.md)

The release handoff contains the portable executable, named qualification
inputs, website integration material, installer guidance, and release
evidence. Historical experiments remain in `experiments/` and are not runtime
dependencies.
