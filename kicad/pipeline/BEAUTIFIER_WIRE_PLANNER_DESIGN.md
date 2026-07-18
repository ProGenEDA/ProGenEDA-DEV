# Beautifier, Arrangement Decider, And Wire Planner Design

Date started: 2026-07-02

## Codex 5.6 Active Implementation Note

This document preserves the original stage design and upgrade thinking. Codex
5.6 converted its core ideas into the active movement-first pipeline: component
coordinates are scored before full routing, rotations and compact square-like
arrangements are considered, terminal fallback is explicit, and the emitted
schematic is checked by actual pin/net/geometry validators. The 5.6 advance
over the earlier 5.5-era plan is that these are now executable, audited stages
with corpus and KiCad application evidence, while the later sections retain
future research directions without weakening the shipped path.

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
- minimum unroutable/partial nets
- acceptable wire length
- acceptable corner count
- stable placement after repeated passes

The current implementation only creates the first JSON contracts. It does not
yet run an automatic loop. The first KiCad wire maker consumes the current
single-pass wire-plan JSON and records any route-cap or pin-resolution limits in
project manifests.

## Wire Planner Current Implementation

File:

```text
kicad/pipeline/wire_planner.py
```

Current behavior:

1. Builds exact endpoint coordinates from placement `pin_points` when available.
2. Reserves exact pin grid cells so unrelated wires do not pass through pins.
3. Routes strict wire mode without local labels.
4. Tries deterministic lane candidates before A*:
   - direct orthogonal paths
   - one-lane doglegs
   - two-lane rectangular doglegs for pin escape plus bus-style channels
5. Scores candidates primarily by component body hits, component shadow
   clearance, routeability, turns, and length. Wire-wire crossings are allowed
   and are no longer a hard validation target.
6. Routes multi-endpoint nets from the nearest already connected endpoint.
7. Orders nets by clock, bus/long-span nets, ordinary nets, then power/ground
   in strict wire mode.
8. Generates and scores arrangement variants before final route search:
   - base topology layout
   - wider column spacing
   - taller row spacing
   - loose grid spacing
   - compact flow spacing
   - dense escape/channel profiles when needed
9. Uses fast routeability scoring for variants:
   - component body overlaps
   - estimated blocked endpoints
   - estimated wire/body hits
   - estimated route length and turn count
10. Evaluates variants in parallel when the design is large enough.
11. Full-routes only the selected moved placement.
12. Uses dense-design mode for large sheets:
   - component threshold: 90 bodies
   - bounded dense lane candidate budget
   - bounded dense A* expansion budget
   - cached obstacle grids
   - grid contact scoring instead of exact segment-pair scoring
   - failed endpoint retry budget before reporting a net incomplete
13. Emits route-level quality metadata:
   - selected router
   - body hit count
   - component shadow count
   - different-net crossing/contact count as a metric only
   - same-net reuse count
   - length and turn count
14. Emits `partial_wire` for strict wire-mode nets where some branches were
    physically routed but one or more endpoints remain unrouted.

Current limits:

1. Dense large schematics can still leave partial or unroutable nets.
2. The planner does not yet move components from route-failure feedback and
   reroute the moved placement.
3. The planner does not yet rip up an already selected route and reroute it
   after later congestion appears.
4. Power/GND nets with very high fanout are intentionally still physical-wire
   attempts in strict wire mode; practical final schematics will likely use the
   terminal/combination path for those nets.
5. `partial_wire` is a failure state for final validation. It exists so the
   wire maker can draw successful physical branches while validators report the
   missing endpoints clearly.

The current router now puts component-motion planning ahead of final route
search. It generates coordinate variants, scores moved placements with a fast
routeability estimate, and full-routes the best variant. This is also the
foundation for the future "variation" feature: multiple valid arrangements of
the same circuit can be kept as scored variants.

The next router upgrade should add targeted second-pass local movement for the
remaining partial nets. It should identify the blocked endpoint/component pair,
generate local nudges, re-score only those local variants, and full-route the
best fix candidate.

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

- move components before route search to avoid blocked pin escapes
- increase vertical spacing for dense nets
- move high-degree components toward the center of their block
- split a large circuit into functional blocks
- switch long high-fanout nets to labels
- reserve channels for buses and clocks
- generate arrangement variations and score them by routeability

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
7. Allows wire-wire crossings; existing wires are not hard obstacles.
8. Keeps existing-wire contacts as metrics only.
9. Routes clock-like nets before ordinary nets.
10. Uses local labels instead of long wires for power, ground, and high-fanout
    nets.
11. Bounds A* search with `max_astar_expansions`; difficult routes fall back to
    a simple orthogonal Manhattan route and record
    `astar_fallback_expansion_limit`.
12. Batch/report runs may set `max_wired_routes`; remaining routes are marked
    `deferred_after_route_limit` instead of blocking the whole run.
13. Reports route metrics and warnings.

Important current limitation:

The wire planner is now bounded and testable, and the KiCad wire maker can draw
its output, but routing is not final-quality yet. `partial_wire` nets,
unroutable nets, and wire/body contacts are evidence that the planner needs
component-motion feedback before route search.

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
    "wire_collision_policy": "wire-wire crossings are allowed; existing wires are congestion metrics only"
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

## KiCad Wire Maker

File:

```text
kicad/pipeline/kicad_wire_maker.py
```

Purpose:

The KiCad wire maker is the first EDA-specific drawing stage. It receives the
same final CircuitIR JSON, the beautified placement, and the pure JSON
`wire_plan`. It does not make routing decisions. It turns the route plan into
actual KiCad schematic objects:

1. Resolves each placed component to its real KiCad `lib_id`.
2. Reads source-backed embedded symbol text through `KiCadSymbolLibrary`.
3. Parses real pin numbers, names, units, and local pin coordinates.
4. Resolves final-JSON pin names through explicit aliases where the logical name
   differs from the KiCad symbol pin name.
5. Converts local symbol pin coordinates to sheet coordinates.
6. Draws KiCad `(wire ...)` objects for routed paths and local labels.
7. Draws KiCad `(junction ...)` objects where three or more same-plan segments
   meet.
8. Draws KiCad label text objects for local-label strategy nets.
9. Records unresolved pin aliases, fallback routes, deferred nets, and planner
   warning counts in each `manifest.json`.

This stage is KiCad-specific by design. Equivalent Proteus or future EDA
backends should consume the same `wire_plan` JSON and implement their own file
writer.

## Wire Geometry Validator

File:

```text
kicad/pipeline/wire_geometry_validator.py
```

Purpose:

The wire geometry validator checks the actual segments emitted by a wire maker.
It is independent of KiCad S-expressions and does not route anything.

Hard rules:

1. Wires must be horizontal or vertical.
2. Wires may cross or touch other wires.
3. Wires must not touch component bodies except at the intended pin point.

The KiCad wire maker records this validator under
`manifest.json -> wire_maker -> wire_geometry_validator`. A generated schematic
is not accepted as final wiring unless this validator passes.

Current generated evidence:

```text
kicad/examples/final_json_wired_project_run_2026_07_02_135608_t01_t10_connected_wired_v4/
```

Result:

- 10 KiCad wired project folders generated from connected final JSON.
- Static schematic quality passed 10/10 with `--skip-erc`.
- `kicad_cli` was not available to this checker run, so ERC was not executed.
- 430 components became 442 symbol instances.
- 3357 wire objects and 530 labels were written.
- T01-T06 and T09 have zero unresolved pins.
- T10 has zero unresolved pins and five deferred nets from the current bounded
  route cap: `SPI_MISO`, `USB1_D_MINUS`, `USB1_D_PLUS`, `USB2_D_MINUS`,
  `USB2_D_PLUS`.
- The remaining 18 unresolved pins are known symbol-model gaps: two artificial
  `LM358.BIAS` endpoints in T07, plus LED-array and DIP-common endpoints in T08
  where the current selected KiCad symbols do not expose the requested logical
  pins.

Current geometry-rule evidence:

```text
kicad/examples/final_json_wired_project_run_2026_07_02_171521_t01_t10_connected_wired_v9_reserved_pin_router/
```

Result:

- Static schematic quality passed 10/10.
- Bundled KiCad CLI loaded all 10 schematics.
- KiCad netlist export succeeded 10/10.
- KiCad ERC quality gate passed 5/10. Remaining blocking issues are logical
  and symbol-model issues, not wire-geometry issues: mostly `multiple_net_names`,
  `label_dangling`, `unconnected_wire_endpoint`, and a few `pin_to_pin` reports.
- Geometry rule gate passed 10/10.
- Total geometry violations: 0.
- Therefore the current wire planner/maker output is geometry-clean and
  openable/exportable, but still not final electrical acceptance until expected
  netlist comparison and ERC repair are implemented.

Failure and improvement records:

- `final_json_wired_project_run_2026_07_02_164836_t01_t10_connected_wired_v5_geometry_rules`
  added the strict validator and correctly rejected the old router: 21268
  geometry violations, ERC gate 1/10.
- `final_json_wired_project_run_2026_07_02_170327_t01_t10_connected_wired_v6_exact_pin_planner`
  fed source-backed KiCad pin/body JSON to the pure planner and reduced
  violations to 14587.
- `final_json_wired_project_run_2026_07_02_170940_t01_t10_connected_wired_v7_strict_router`
  removed speculative Manhattan fallback wires, added 1.27 mm routing, and
  reduced violations to 9.
- `final_json_wired_project_run_2026_07_02_171210_t01_t10_connected_wired_v8_pin_side_fix`
  fixed outside-pin side detection and reduced violations to 2.
- `final_json_wired_project_run_2026_07_02_171521_t01_t10_connected_wired_v9_reserved_pin_router`
  reserves exact pin cells and restricts pin corridors to the endpoint
  component, reaching 0 geometry violations.

Run:

```bash
python -m kicad.pipeline.kicad_wire_maker kicad/examples/final_json_run_2026_07_02_132530_t01_t10_connected_v3/final_json --examples-root kicad/examples --label t01_t10_connected_wired_v4
PYTHONPATH=. python -m kicad.automation.quality_check kicad/examples/final_json_wired_project_run_2026_07_02_135608_t01_t10_connected_wired_v4 --skip-erc
python -m kicad.pipeline.kicad_wire_maker kicad/examples/final_json_run_2026_07_02_132530_t01_t10_connected_v3/final_json --examples-root kicad/examples --label t01_t10_connected_wired_v5_geometry_rules
PYTHONPATH=. python -m kicad.automation.quality_check kicad/examples/final_json_wired_project_run_2026_07_02_164836_t01_t10_connected_wired_v5_geometry_rules --export-netlist
python -m kicad.pipeline.kicad_wire_maker kicad/examples/final_json_run_2026_07_02_132530_t01_t10_connected_v3/final_json --examples-root kicad/examples --label t01_t10_connected_wired_v9_reserved_pin_router
PYTHONPATH=. python -m kicad.automation.quality_check kicad/examples/final_json_wired_project_run_2026_07_02_171521_t01_t10_connected_wired_v9_reserved_pin_router --export-netlist
```

## Routing Rules To Preserve

The wire planner should keep these priorities:

1. No overlapping components.
2. Pin connections must be exact.
3. Signal flow left to right.
4. Move components before route search when routeability needs it.
5. Avoid wire runs through component bodies.
6. Minimize unroutable and partial-wire nets.
7. Keep wires horizontal or vertical.
8. Minimize wire length after routeability is satisfied.
9. Avoid 4-way junctions when easy.
10. Route feedback below the main signal path.
11. Route clock nets early.
12. Use terminal/combination mode for long power/ground/high-fanout nets when
    strict physical wire mode is not required.
13. Prefer fewer corners.
14. Preserve readable labels and component values.

When rules conflict:

```text
component/body validity > exact pins > complete nets > signal flow > wire length > alignment > wire-wire crossings
```

## Current Tests

The focused tests live in:

```text
kicad/tests/test_placer_pipeline.py
kicad/tests/test_kicad_wire_maker.py
```

Current coverage:

1. Arrangement decider emits topology coordinate plans.
2. Beautifier applies coordinate edits and moves obstacle boxes.
3. Wire planner emits both coordinate and A* wire JSON.
4. Power/ground nets become local labels.
5. Ordinary signal routes are orthogonal.
6. Routed segments do not cross unrelated component bodies in the test circuit.
7. Different-net crossing count is reported as a quality metric only.
8. Connected T01-T10 final JSON inputs compile, place, beautify without body
   overlaps, and produce bounded wire-plan reports.
9. The KiCad wire maker emits real wire/label objects and can generate fresh
   immutable wired project runs from final JSON.
10. The net extractor accepts both `ref:pin` and `ref.pin` endpoint notation.
11. The wire planner prefers supplied exact pin points over estimated component
    edge stubs.
12. The wire-geometry validator allows wire-wire crossings and rejects
    component body touches away from intended pins.

## T01-T10 Evidence

The first T01-T10 stress check is recorded in:

```text
kicad/experiment_records/runs/beautifier_wire_planner_t01_t10_2026_07_02/
```

Result:

- Wire planner smoke test on connected VDC -> resistor -> LED -> GND passed.
- T01-T10 arrangement/beautifier passed 10/10.
- Post-beautifier overlap count was 0 for all 10.
- T01-T10 wire route count was 0 because those stress inputs are still
  placement-only and contain no `components[].pins` connection endpoints.

The first connected final-JSON run is recorded in:

```text
kicad/examples/final_json_run_2026_07_02_132530_t01_t10_connected_v3/
```

Result:

- Final JSON validation passed 10/10.
- Placer input conversion passed 10/10.
- Arrangement and beautifier passed 10/10 with 0 post-beautifier body overlaps.
- Bounded wire-plan reports were produced for all 10.
- T10 compiled to 190 components, 153 nets, and 554 endpoints.
- The route reports include fallback/crossing warnings. These are current wire
  planner quality limits, not JSON or placement failures.

The first accepted KiCad wired project run is recorded in:

```text
kicad/examples/final_json_wired_project_run_2026_07_02_135608_t01_t10_connected_wired_v4/
```

Result:

- 10/10 static schematic checks passed.
- KiCad wire/label/junction objects are present in all 10 schematics.
- Pin resolution is complete for T01-T06, T09, and T10.
- Known gaps remain for T07/T08 symbol modeling and T10 route-cap deferrals.

The first strict geometry-rule run is recorded in:

```text
kicad/examples/final_json_wired_project_run_2026_07_02_164836_t01_t10_connected_wired_v5_geometry_rules/
```

Result:

- The new wire-geometry validator correctly rejects the current routed outputs.
- KiCad netlist export succeeds, so KiCad can parse/export the files.
- ERC confirms these are not final-correct schematics yet.

The current strict router run is recorded in:

```text
kicad/examples/final_json_wired_project_run_2026_07_02_171521_t01_t10_connected_wired_v9_reserved_pin_router/
```

Result:

- Static schematic quality passed 10/10.
- KiCad netlist export passed 10/10.
- Geometry validation passed 10/10 with 0 violations.
- ERC quality passed 5/10. Remaining failures are the next work item and are
  mainly caused by label-heavy fallback nets and unresolved logical symbol
  models, not by wires crossing or touching bodies.

Run:

```bash
PYTHONPATH=. python -m unittest kicad.tests.test_final_circuit_builder kicad.tests.test_kicad_wire_maker kicad.tests.test_placer_pipeline -v
PYTHONPATH=. python -m unittest kicad.tests.test_wire_geometry_validator -v
python -m compileall -q kicad/pipeline kicad/tests kicad/automation
```

## Not Implemented Yet

These are intentionally future work:

1. Automatic wire-planner/beautifier iterative loop.
2. Beautifier validator.
3. Terminal placer expansion beyond the current KiCad local-label foundation.
4. Bus routing.
5. Pattern-template placement.
6. Rotation optimization.
7. Feedback-loop routing below the main path.
8. Better symbol models for LED arrays, DIP common pins, and artificial op-amp
   bias nodes.
9. Expected-net comparison against exported KiCad netlists.
10. ERC-backed repair for label-heavy fallback nets.
11. Final validation report.

## 2026-07-03 Routing-Mode Boundary Update

`routing_mode` is now explicit in final CircuitIR JSON and wire-plan JSON:

- `wire` mode forbids local-label strategies. The planner records `unroutable`
  failures instead of silently converting failed routes to labels, and the KiCad
  wire maker reports strict wire connectivity by walking the actual
  wire/junction/pin graph.
- `terminal` mode is owned by `kicad/pipeline/terminal_placer.py`; its current
  KiCad backend is local labels with short pin stubs.
- `combination` mode may use both routed wires and terminal/local-label plans.

The strict wire validator ignores labels and requires every expected net
endpoint to be connected through physical wire segments. It also unions same-net
T-junction/interior segment contacts so valid wire trunks are not falsely
reported as disconnected.

Current strict-wire status: the router now draws more physical wires and no
labels in wire mode, but the routed Proteus-alias suite still reports unroutable
nets and wire-geometry violations. Do not publish a new accepted strict-wire
example run until both `strict_wire_ok` and `geometry_ok` pass for every
generated project. Combination mode remains useful as label-assisted evidence,
but it is not strict wire acceptance.

## Core Principle

The goal is not just rule compliance. The goal is that a human engineer can look
at the generated schematic and quickly understand the circuit without confusion.
