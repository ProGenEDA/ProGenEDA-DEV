# Mixed Passive JSON Input

The locked mixed resistor/capacitor generator accepts strict JSON. It does not parse free-form English.

Command:

```powershell
proteusgen generate-mixed-passives path\to\mixed_passive.json --outdir out\mixed_passive
```
Current contract:

```text
schema_version: proteus-mixed-passive-ir/v0.1
generator_target: proteus-8.13-mixed-passive-terminal-power-ground
base: E001_EMPTY_BASE
units: proteus_internal
node labels: exactly two ASCII characters
component refs: exactly two ASCII characters
supported components: RESISTOR, CAPACITOR
power node: V0 with kind=power
ground node: G0 with kind=ground
```

Power and ground behavior:

```text
V0 -> one donor-derived $TERPOWER -> $TEROUTPUT(V0) bridge
component endpoint on V0 -> ordinary $TERINPUT(V0), and only on nodes[0]
component endpoint on G0 -> $TERGROUND(G0), and only on nodes[1]
```

Layout behavior:

```text
manual coordinates are placement hints
minimum safe x/y spacing is 2540000 internal units
duplicate positions are shifted so components do not overlap
standalone visual_wires are parsed but skipped
```

Minimal example:

```json
{
  "schema_version": "proteus-mixed-passive-ir/v0.1",
  "generator_target": "proteus-8.13-mixed-passive-terminal-power-ground",
  "project": {
    "name": "MIXED_RC_EXAMPLE",
    "output_basename": "MIXED_RC_EXAMPLE",
    "base": "E001_EMPTY_BASE",
    "units": "proteus_internal"
  },
  "nodes": [
    {"id": "V0", "kind": "power"},
    {"id": "N1", "kind": "internal"},
    {"id": "G0", "kind": "ground"}
  ],
  "components": [
    {"ref": "R1", "type": "RESISTOR", "value": "1k", "nodes": ["V0", "N1"]},
    {"ref": "C2", "type": "CAPACITOR", "value": "1uF", "nodes": ["N1", "G0"]}
  ],
  "layout": {
    "mode": "manual_component_positions",
    "coordinate_units": "proteus_internal",
    "component_positions": {
      "R1": {"x": -6350000, "y": 5080000},
      "C2": {"x": -3810000, "y": 5080000}
    }
  },
  "metadata": {}
}
```
