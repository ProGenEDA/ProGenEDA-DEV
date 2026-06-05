# Resistor JSON Input

The V9 resistor generator takes a JSON file path as input. It does not parse free-form English.

Supported command forms:

```powershell
python generate_from_json.py --input examples\resistor_v9_power_ground.json --outdir out\resistor_case
proteusgen generate-resistors examples\resistor_v9_power_ground.json --outdir out\resistor_case
```

The JSON contract is:

```text
schema_version: proteus-circuit-ir/v0.1
generator_target: proteus-8.13-v9-resistor-terminal
base: E001_EMPTY_BASE
components: RESISTOR only
node labels: exactly two ASCII characters
refs: exactly two ASCII characters
```

Current power/ground convention:

```text
V0 with kind=power  -> one donor-derived $TERPOWER -> $TEROUTPUT(V0) bridge
component.nodes[0]  -> normal $TERINPUT(V0) endpoint when the node is V0
G0 with kind=ground -> $TERGROUND when used as component.nodes[1]
```

Do not use `VCC`, `GND`, `R10`, or other longer labels in v0.1. Use `V0`, `G0`, `RA`, `RB`, etc.

Visual orientation is controlled per resistor through `visual.orientation_hint`:

```json
{
  "ref": "R1",
  "type": "RESISTOR",
  "value": "1k",
  "nodes": ["V0", "G0"],
  "visual": {"orientation_hint": "vertical"}
}
```

Supported hints are `horizontal`, `vertical`, `vertical_up`, `left`, and their aliases in the schema. `vertical` writes the real Proteus `-900` tenths-of-degrees angle field and makes the short-wire endpoint stubs vertical.

Minimal example:

```json
{
  "schema_version": "proteus-circuit-ir/v0.1",
  "generator_target": "proteus-8.13-v9-resistor-terminal",
  "project": {
    "name": "SINGLE_R_POWER_GROUND",
    "output_basename": "SINGLE_R_POWER_GROUND",
    "base": "E001_EMPTY_BASE",
    "units": "proteus_internal"
  },
  "nodes": [
    {"id": "V0", "kind": "power"},
    {"id": "G0", "kind": "ground"}
  ],
  "components": [
    {"ref": "R1", "type": "RESISTOR", "value": "1k", "nodes": ["V0", "G0"]}
  ],
  "layout": {
    "mode": "manual_component_positions",
    "coordinate_units": "proteus_internal",
    "component_positions": {
      "R1": {"x": -6350000, "y": 5080000}
    }
  },
  "metadata": {}
}
```

Electrical authority is `components[*].nodes`. Layout places the first resistor pin; the generator derives the second pin, terminal positions, short-wire stubs, and the single power bridge from the node metadata.

Manual `layout.component_positions` values are placement hints. If multiple requested positions are packed too closely, production generation stretches them to the safe V9 grid before emitting `ROOT.DSN` so terminals and resistor bodies do not overlap.

`layout.visual_wires` may appear in JSON for future bus/junction drawing, but production generation currently skips those records because unvalidated standalone wires were linked to VGDVC failures. Component endpoints and node labels remain the electrical authority:

```json
"visual_wires": [
  {"x1": -6350000, "y1": 5080000, "x2": -2540000, "y2": 5080000}
]
```
