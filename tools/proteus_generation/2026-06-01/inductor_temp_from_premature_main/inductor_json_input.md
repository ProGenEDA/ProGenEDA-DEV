# Inductor JSON Input

Use this contract with:

```bash
python -m proteusgen generate-inductors examples/inductor_locked_t02_single_power_ground.json --outdir out/inductor_test
```

The generated `.pdsprj` will be written to the output directory named by `project.output_basename`.

## Required Top-Level Fields

- `schema_version`: must be `proteus-inductor-ir/v0.1`
- `generator_target`: must be `proteus-8.13-inductor-terminal-power-ground`
- `project.base`: must be `E001_EMPTY_BASE`
- `project.units`: must be `proteus_internal`
- `nodes`: two-character node labels only
- `components`: one to three `INDUCTOR` components
- `layout.component_positions`: Proteus internal integer coordinates unless `layout.auto_place` is true

## Locked Scope

The accepted inductor methods are intentionally narrow:

- Terminal-only inductor networks: one to three inductors using `$TERINPUT` and `$TEROUTPUT` label topology.
- Power/ground inductor: exactly one inductor with `nodes: ["V0", "G0"]`.
- Power/ground uses the accepted donor04 object order: input internal node, `REALIND`, left wire, `$TERPOWER`, `$TEROUTPUT` internal node, bridge wire, `$TERGROUND`, final ground wire.
- Multi-inductor circuits that include V0 or G0 are rejected until a Proteus-tested method exists.
- The generic passive power bridge is not used for inductors.

## Example: Single Power/Ground Inductor

```json
{
  "schema_version": "proteus-inductor-ir/v0.1",
  "generator_target": "proteus-8.13-inductor-terminal-power-ground",
  "project": {
    "name": "Single V0 G0 inductor",
    "output_basename": "inductor_locked_t02_single_power_ground",
    "base": "E001_EMPTY_BASE",
    "units": "proteus_internal"
  },
  "nodes": [
    {"id": "V0", "kind": "power"},
    {"id": "G0", "kind": "ground"}
  ],
  "components": [
    {
      "ref": "LA",
      "type": "INDUCTOR",
      "value": "2mH",
      "nodes": ["V0", "G0"],
      "visual": {"internal_power_node": "B1"}
    }
  ],
  "layout": {
    "mode": "manual_component_positions",
    "coordinate_units": "proteus_internal",
    "component_positions": {
      "LA": {"x": -7366000, "y": 1270000}
    },
    "visual_wires": [],
    "auto_place": false
  },
  "metadata": {}
}
```
