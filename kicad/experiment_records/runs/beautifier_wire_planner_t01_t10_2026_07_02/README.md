# Beautifier/Wire Planner T01-T10 Evidence

Date: 2026-07-02

## What Was Tested

1. Wire planner smoke test on a connected VDC -> resistor -> LED -> GND circuit.
2. Arrangement decider on stress circuits T01 through T10 from `kicad/examples/placer_run_2026_07_01_stress_limit_suite_v2/inputs`.
3. Beautifier coordinate application on the same T01 through T10 placements.

## Important Wire Result

The T01-T10 stress inputs are placement-only. They have `nets: {}` and no `components[].pins`, so the wire planner has no must-make connection endpoints for those ten circuits. It correctly produced zero wire routes for those inputs.

A separate connected smoke circuit was checked first:

- wire smoke passed: `True`
- net count: `3`
- routed wires: `2`
- segments: `2`
- different-net crossings: `0`
- GND strategy: `local_labels`

## Arrangement/Beautifier Result

- T circuits checked: `10`
- total components checked: `537`
- arrangement/beautifier pass count: `10`
- max post-beautifier overlap count: `0`
- wire-planned T circuits: `0`
- wire-skipped T circuits due missing connection data: `10`

The arrangement decider now packs coordinates using actual component body sizes. The beautifier applies the coordinate edits and translates obstacle boxes without changing component identity or generating KiCad files.

## Output Files

- `t01_t10_stage_report.json`
- `connected_wire_smoke_report.json`

## Next

To route T01-T10 for real, those inputs need pin/net data or a component-selector/JSON-enhancer stage that adds must-make connections.
