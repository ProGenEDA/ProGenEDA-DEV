# Beautifier, Arrangement Decider, And Wire Planner Design

Date started: 2026-07-02

This document records the intended behavior for the next KiCad pipeline stages
after the component placer. It captures the user requirements, the current
implementation, and the upgrade path.

## Current Validator

The current validator is a placement-stage validator only. It is not the final
schematic correctness validator.

Current checks:

1. Input JSON shape is usable for placement.
2. Component kinds are supported by the placement catalog or source-backed
   generator specs.
3. Pin numbers are checked when the input provides pins and the source-backed
   kind has pin metadata.
4. Every requested component receives a placement.
5. Component references are unique at input validation time.
6. Component body obstacle boxes do not overlap.
7. Generated KiCad schematics are statically checked by existing quality tools
   when a project is written.

This validates that the placer produced a structurally usable placement. It does
not prove that the final circuit is electrically complete.

## Future Validation Pipeline

Future validators should be added as producing stages become real:

```text
1. File validity
2. Component count/reference/value check
3. Pin existence check
4. Netlist export
5. Expected-net comparison
6. ERC
7. Optional PDF/SVG preview export
8. Final validation_report.json
```

The final validator should not rely on visual assumptions. It should compare the
expected logical circuit against the exported EDA netlist and KiCad ERC output.

## Pipeline Position

The full intended flow remains:

```text
Prompt
Prompt Enhancer
Enhanced Prompt to Script-Understandable JSON
JSON Enhancer
JSON Validator
File Name Decider
Arrangement Decider
Component Selector
Validator
Component Placer
Placement Validator
User Specification Validator
Beautifier
Beautifier Validator
Decision: Wire / Terminal / Combination
```

Wire path:

```text
Decision -> Wire Planner <-> Beautifier loop -> Wire Maker -> Value Editor -> Value Validator -> Final Validator -> Output
```

Terminal path:

```text
Decision -> Terminal Placer -> Value Editor -> Value Validator -> Final Validator -> Output
```

Combination path:

```text
Decision -> Combination Decider -> Wire Planner <-> Beautifier loop -> Wire Maker -> Terminal Placer -> Terminal Validator -> Value Editor -> Value Validator -> Final Validator -> Output
```

## Stage Independence Rules

These stages must stay independent:

- `arrangement_decider.py` decides first-pass coordinates.
- `beautifier.py` only edits coordinates.
- `wire_planner.py` is pure math and JSON.
- EDA-specific file drawing belongs to a later wire maker.
- KiCad S-expressions, Proteus files, and GUI behavior must not leak into the
  wire planner.

The wire planner must be easy to reuse with a different EDA backend by replacing
only the small config values for sheet size, grid, clearance, and similar
geometry parameters.

## Arrangement Decider

File:

```text
kicad/pipeline/arrangement_decider.py
```

Purpose:

The arrangement decider makes the first coordinate decision after placement. It
does not edit the placement JSON itself. It emits coordinate-plan JSON for the
beautifier.

Implemented behavior:

1. Extracts connections from CircuitIR-style inputs:
   - `components[].pins`
   - `nets` endpoint lists when present
2. Builds a component graph.
3. Classifies component roles:
   - power
   - ground
   - terminal
   - passive
   - processing
   - load
   - leaf
4. Applies a layered layout inspired by the Sugiyama algorithm:
   - signal flow tends left to right
   - graph depth decides X position
   - barycenter ordering reduces crossings within layers
5. Applies schematic conventions:
   - power symbols above signal flow
   - ground symbols below signal flow
   - terminals and sources toward the left
   - loads toward the right
6. Detects clock-like nets by name and records a routing priority warning.
7. Records a density warning when component count exceeds 50.
8. Snaps planned coordinates to the configured grid.

Important future upgrades:

1. Add force-directed refinement for irregular graphs.
2. Add rotation scoring for 0, 90, 180, and 270 degrees.
3. Add pattern templates:
   - RC lowpass
   - RC highpass
   - voltage divider
   - H-bridge
   - 555 astable
   - op-amp inverting/non-inverting amplifier
   - counter cascades
   - 7-segment decoder/display blocks
4. Add functional block detection for large circuits.
5. Add explicit feedback-loop detection and routing hints.

Coordinate-plan JSON schema:

```json
{
  "schema": "progen-kicad-arrangement-decision/v0.1",
  "stage": "arrangement_decider",
  "algorithm": {
    "primary": "sugiyama_layered_layout",
    "ordering": "barycenter_crossing_minimization"
  },
  "sheet": {
    "width": 420.0,
    "height": 297.0,
    "grid": 2.54,
    "margin": 25.4
  },
  "layers": {
    "0": ["V1"],
    "1": ["R1"],
    "2": ["D1"]
  },
  "components": {
    "R1": {
      "kind": "R",
      "role": "passive",
      "original_at": [58.42, 25.4],
      "planned_at": [71.12, 147.32],
      "size": [7.0, 2.5]
    }
  },
  "coordinate_edits": [
    {
      "ref": "R1",
      "from": [58.42, 25.4],
      "to": [71.12, 147.32],
      "delta": [12.7, 121.92],
      "rotation": 0.0,
      "reason": ["topology_depth_to_x", "barycenter_row_order"]
    }
  ],
  "warnings": []
}
```

## Beautifier

File:

```text
kicad/pipeline/beautifier.py
```

Purpose:

The beautifier is only a coordinate editor. It applies coordinate-plan JSON and
returns a new placement JSON object. It must not invent layout logic or routing
logic.

Implemented behavior:

1. Reads `coordinate_edits`.
2. Updates `components[ref].at`.
3. Updates `components[ref].rotation` when the edit provides it.
4. Translates matching obstacle boxes by the same delta.
5. Records `applied_edits`.

Beautified placement JSON schema:

```json
{
  "schema": "progen-kicad-beautified-placement/v0.1",
  "stage": "beautifier",
  "components": {},
  "obstacles": [],
  "applied_edits": [],
  "source_coordinate_plan_schema": "progen-kicad-arrangement-decision/v0.1"
}
```

## Beautifier And Wire Planner Loop

The intended loop is:

```text
Wire Planner -> coordinate-plan JSON -> Beautifier -> Beautifier Validator -> Wire Planner
```

The loop continues until the wire planner can route the circuit with acceptable
metrics:

- no component overlaps
- no wire through component bodies
- minimal crossings
- acceptable wire length
- acceptable corner count
- stable placement after repeated passes

The current implementation only creates the first JSON contracts. It does not
yet run an automatic loop.

## Wire Planner

File:

```text
kicad/pipeline/wire_planner.py
```

Purpose:

The wire planner is a pure mathematical JSON unit. It receives:

1. A placement JSON file with component coordinates, sizes, and obstacle boxes.
2. The main CircuitIR-style JSON file with must-make connections.

The main JSON is the same high-level circuit JSON used by other stages. The
wire planner only consumes the connection information it needs, especially
matching net names from component pins and net endpoint lists.

The wire planner emits two JSON outputs:

```text
wire_coordinate_plan.json
wire_plan.json
```

### Output 1: Coordinate Plan

The first output tells the beautifier how components should be rearranged so
wiring can become cleaner. This output is generated by calling the arrangement
decider from the wire planner and returning the same coordinate-plan contract.

Current schema:

```text
progen-kicad-arrangement-decision/v0.1
```

Future versions should include iterative route feedback, for example:

- move component left/right to reduce crossings
- increase vertical spacing for dense nets
- move high-degree components toward the center of their block
- split a large circuit into functional blocks
- switch long high-fanout nets to labels
- reserve channels for buses and clocks

### Output 2: Wire Plan

The second output contains the actual wiring scheme for a later wire maker.

Current schema:

```text
progen-kicad-wire-plan/v0.1
```

Implemented behavior:

1. Extracts net endpoints from `components[].pins` and endpoint-style `nets`
   when present.
2. Computes pin-attachment points from component bodies.
3. Assigns attachment side:
   - power nets attach upward
   - ground nets attach downward
   - ordinary signals attach toward connected components
4. Routes ordinary nets with grid-based A*.
5. Uses only orthogonal horizontal/vertical segments.
6. Inflates component bodies as obstacles.
7. Avoids existing different-net wires with a high cost.
8. Adds adjacency penalty near existing different-net wires.
9. Routes clock-like nets before ordinary nets.
10. Uses local labels instead of long wires for power, ground, and high-fanout
    nets.
11. Reports route metrics and warnings.

Wire-plan JSON shape:

```json
{
  "schema": "progen-kicad-wire-plan/v0.1",
  "stage": "wire_planner",
  "input_contract": {
    "placement": "components plus obstacles JSON; no EDA file required",
    "connections": "CircuitIR components[].pins and/or nets endpoint lists"
  },
  "algorithm": {
    "router": "grid_astar_orthogonal",
    "routing_order": "clock, ordinary short nets, power/ground labels, high-fanout labels",
    "component_avoidance": "inflated_obstacle_grid",
    "wire_collision_policy": "different-net existing wires receive high cost plus adjacency penalty"
  },
  "sheet": {
    "width": 420.0,
    "height": 297.0,
    "grid": 2.54,
    "clearance": 2.54
  },
  "nets": {
    "LED_A": {
      "strategy": "wire",
      "endpoints": [],
      "routes": []
    },
    "GND": {
      "strategy": "local_labels",
      "endpoints": [],
      "routes": []
    }
  },
  "routes": [
    {
      "net": "LED_A",
      "from": {"ref": "R1", "pin": "2", "point": [62.23, 25.4]},
      "to": {"ref": "D1", "pin": "1", "point": [78.74, 25.4]},
      "path": [[62.23, 25.4], [78.74, 25.4]],
      "segments": [
        {
          "start": [62.23, 25.4],
          "end": [78.74, 25.4],
          "direction": "right",
          "length": 16.51
        }
      ]
    }
  ],
  "metrics": {
    "net_count": 3,
    "wired_route_count": 2,
    "segment_count": 2,
    "different_net_crossing_count": 0
  },
  "warnings": []
}
```

## Routing Rules To Preserve

The wire planner should keep these priorities:

1. No overlapping components.
2. Pin connections must be exact.
3. Signal flow left to right.
4. Minimize crossings.
5. Minimize wire length.
6. Keep wires horizontal or vertical.
7. Avoid wire runs through component bodies.
8. Avoid 4-way junctions.
9. Route feedback below the main signal path.
10. Route clock nets first.
11. Use labels for long power/ground/high-fanout nets.
12. Prefer fewer corners.
13. Preserve readable labels and component values.

When rules conflict:

```text
component/body validity > exact pins > signal flow > crossings > wire length > alignment
```

## Current Tests

The focused tests live in:

```text
kicad/tests/test_placer_pipeline.py
```

Current coverage:

1. Arrangement decider emits topology coordinate plans.
2. Beautifier applies coordinate edits and moves obstacle boxes.
3. Wire planner emits both coordinate and A* wire JSON.
4. Power/ground nets become local labels.
5. Ordinary signal routes are orthogonal.
6. Routed segments do not cross unrelated component bodies in the test circuit.
7. Different-net crossing count is reported.

Run:

```bash
python -m unittest kicad.tests.test_placer_pipeline -v
python -m compileall -q kicad/pipeline kicad/tests
```

## Not Implemented Yet

These are intentionally future work:

1. Automatic wire-planner/beautifier iterative loop.
2. Beautifier validator.
3. EDA-specific wire maker.
4. KiCad wire drawing.
5. Terminal placer integration.
6. Junction-dot generation.
7. Net-label placement in KiCad.
8. Bus routing.
9. Pattern-template placement.
10. Rotation optimization.
11. Feedback-loop routing below the main path.
12. Final netlist export and expected-net comparison.

## Core Principle

The goal is not just rule compliance. The goal is that a human engineer can look
at the generated schematic and quickly understand the circuit without confusion.
