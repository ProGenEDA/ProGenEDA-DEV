# Deterministic Circuit Beautifier

## Status

There are two related layout systems:

1. The accepted legacy circuit-route beautifier, used by locked passive,
   RCL, source, and related generators.
2. The newer component-placer packet beautifier, which translates bare donor
   packets through family-registered coordinate parsers.

The V2 legacy beautifier is accepted and is the default for its routes when
layout is omitted. The packet beautifier has passed static and broad Proteus
placement tests, but arrangement quality and later terminal/wire placement are
separate milestones.

The layout stage runs before Proteus binary emission. It translates complete
donor-derived component, terminal, source, and attached short-wire records. It
does not edit a completed `.pdsprj`, synthesize routed buses, or add junctions.

## CircuitIR interface

```json
{
  "layout": {
    "strategy": "beautify",
    "direction": "left_to_right",
    "component_positions": {},
    "source_positions": {}
  }
}
```

Supported strategies:

- `beautify`: deterministic topology-first placement.
- `manual`: exact supplied positions; every generated component and source
  requires a position.
- `legacy`: preserve the accepted route-specific placement method.

Existing payloads with component or source positions and no strategy retain
manual behavior. Payloads without positions default to `beautify`.

## Commands

Plan placement without producing a Proteus project:

```powershell
python -m proteusgen plan-layout circuit.json --layout-strategy beautify
```

Generate with an explicit strategy:

```powershell
python -m proteusgen generate-mixed-rcl circuit.json `
  --outdir out\beautified `
  --layout-strategy beautify
```

Each generated directory contains `layout_plan.json`. The generation manifest
also records strategy, placements, bounds, wrapping, adjustments, detected
motifs, and overlap results.

## Deterministic rules

- Flow direction is left to right.
- Horizontal component spacing is `3175000` Proteus internal units.
- Vertical lane spacing is `2032000` units.
- Long paths wrap after seven component slots.
- `V0` and source-positive nets are roots.
- `G0` and source-negative nets are sinks.
- Parallel paths use separate lanes.
- High-degree nodes, cycles, parallel edges, and same-level bridge/chord edges
  are detected generically.
- CircuitIR endpoint order guides the left-to-right spanning layout. Consecutive
  components sharing the same node label prefer one horizontal lane.
- Sources use a dedicated column one horizontal spacing left of the network.
- Multiple sources stack with `5080000` units of anchor clearance.
- AC source translation keeps the `VSINE` body, visible fields, terminals, and
  attached short-wire records together.
- Explicit resistor orientation is preserved.
- Capacitor, inductor, and source rotations are not invented.
- Object order, suffixes, global IDs, terminators, CDB order, and net labels are
  left to the accepted route emitters.

## Acceptance pack

The original representative pack can be rebuilt with:

```powershell
python tools\proteus_generation\2026-06-06\generate_beautifier_v1_temp.py
```

The output is:

```text
experiments/BEAUTIFIER_V1_REPRESENTATIVE_TEMP_2026_06_06.zip
```

It contains paired legacy and beautified projects for divider, parallel,
series-parallel, delta, star, Wheatstone, R-2R, corrected 21-component,
single-DC, mixed-DC, and AC-voltage cases. The accepted V2 follow-up additionally
verified double-source separation, compact AC-source geometry, and repeated-node
lane continuity.

The post-V3 compacting revision reduces only component column and lane spacing.
It retains the accepted `5080000` multi-source clearance and all overlap checks.

## Removal-only component placer

The newer mega-donor component placer uses a separate packet beautifier. It
moves complete bare component packets through family-registered coordinate
parsers and records every binary translation in
`layout_plan.actual_binary_placements`.

Current rules:

- passive/discrete/source families use proven parsed or linked coordinate paths;
- each IC family must pass an independent packet-profile survey before
  registration;
- broad `component_text_or_body` scanning is rejected for production output;
- `SWITCH` and `POT-HG` use exact requested counts;
- D20 display infrastructure is immutable and retains donor coordinates;
- terminals and wires are not emitted by the component placer.
