# KiCad Pipeline

This package is being built incrementally.

## Active Slice

Current active flow:

```text
CircuitIR JSON -> Placement Input Validator -> Component Placer -> Placement Validator -> KiCad project
```

The active stages are independent:

- `placement_input_validator.validate_placement_input(circuit)`
  checks component kinds and pin numbers against
  `kicad.generator.kicad_json_to_project.KIND_SPECS`.
- `kicad_component_placer.place_components(circuit)`
  is the canonical component placer and does not run routing.
- `placement_validator.validate_placement(circuit, placement_plan)`
  checks that requested components were placed and that component obstacle boxes
  do not overlap.
- `placement_project_writer.write_placement_project(circuit, placement, out_dir)`
  writes an openable `.kicad_pro` and `.kicad_sch` with embedded placement
  symbols.

This active placer slice does not require KiCad to be installed. It uses
embedded Python metadata from the repository:

- source-backed generator specs in `kicad.generator.kicad_json_to_project.KIND_SPECS`
- partial CircuitIR placement specs in `kicad.pipeline.placement_catalog`

The current validator is intentionally only a placement-stage validator. The
future full output validation stack is:

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

## Arrangement, Beautifier, And Wire Planner

The next independent JSON stages are present but not wired into project writing:

- `arrangement_decider.decide_arrangement(placement, circuit)`
  emits a coordinate-plan JSON using topology depth, barycenter ordering,
  power/ground placement, clock detection, and density warnings.
- `beautifier.apply_coordinate_edits(placement, coordinate_plan)`
  applies only coordinate edits and returns a new placement JSON object.
- `wire_planner.plan_wiring(placement, circuit)`
  emits two JSON contracts: `coordinate_plan` for the beautifier and `wire_plan`
  for a later EDA-specific wire maker.

`wire_planner.py` is deliberately pure math/JSON. It does not know about KiCad
S-expressions or Proteus files.

Detailed behavior, JSON contracts, validation expectations, and future routing
rules are recorded in:

```text
kicad/pipeline/BEAUTIFIER_WIRE_PLANNER_DESIGN.md
```

## Final Circuit JSON Compiler

The first deterministic prompt-to-main-JSON slice is:

```text
kicad/pipeline/final_circuit_builder.py
```

Detailed behavior and upgrade path are documented in:

```text
kicad/pipeline/FINAL_CIRCUIT_JSON_COMPILER.md
```

It implements the non-AI part of the requested architecture:

```text
Prompt Cleaner -> raw/block circuit spec -> deterministic net compiler -> universal JSON validator -> final CircuitIR JSON
```

The prompt cleaner normalizes the user prompt and extracts stable hints, but it
does not invent components or nets. AI is only allowed later for intent
extraction and block selection. Final component allocation, net alias repair,
endpoint assignment expansion, duplicate endpoint merging, and final acceptance
are deterministic Python logic.

The compiler currently builds connected final JSON for the ten requested
arrangement/beautifier/wire-planner tests. Generate a fresh immutable run with:

```text
python -m kicad.pipeline.final_circuit_builder --examples-root kicad/examples --label t01_t10_connected_v1
```

Each run writes:

```text
final_json/          canonical connected CircuitIR JSON
placement_inputs/   component-only inputs derived from the final JSON for the placer
stage_reports/      arrangement, beautifier, and wire-planner metrics
run_manifest.json   aggregate evidence
```

The stage reports use bounded route-planning settings for batch evidence. If
the current A* router cannot finish a path within the configured expansion
limit, it emits a fallback route and records an
`astar_fallback_expansion_limit` warning. If the stress report hits the route
count cap, remaining nets are marked `deferred_after_route_limit`. These are
wire-planner limitations to fix before the later EDA-specific wire maker stage.

Old generated run folders remain immutable records.

## Practical Component Pack

Historical early input packs live under:

```text
kicad/examples/placer_pack/
```

Current generated packs live inside immutable run folders, for example:

```text
kicad/examples/placer_run_2026_07_01_baseline_c11_spacing_fix_v2/inputs/
kicad/examples/placer_run_2026_07_01_stress_limit_suite_v2/inputs/
```

Generate a new immutable baseline run with:

```text
mkdir -p kicad/examples/placer_run_<date>_<label>/inputs
python -m kicad.automation.generate_practical_placer_examples --suite baseline --outdir kicad/examples/placer_run_<date>_<label>/inputs
python -m kicad.pipeline.kicad_component_placer kicad/examples/placer_run_<date>_<label>/inputs --run-dir kicad/examples/placer_run_<date>_<label> --run-label <label>
```

These files use `schema_version: progen-kicad-placer-ir/v0.2` and
`compatible_schema: progen-kicad-circuit-ir/v1`. They intentionally include the
same broad shape as full CircuitIR (`project`, `components`, `nets`, component
`id`, `kind`, and `value`) without inventing `pins` or net membership before the
wire planner, terminal placer, and value editor stages exist.

Running the placer on these inputs writes real KiCad project folders:

```text
python -m kicad.pipeline.kicad_component_placer kicad/examples/placer_run_<date>_<label>/inputs --run-dir kicad/examples/placer_run_<date>_<label> --run-label <label>
```

Each generated folder contains `OPEN_THIS_PROJECT__...__PLACER.kicad_pro` and
the matching `.kicad_sch`. The symbols are embedded in the schematic so KiCad
does not need global symbol libraries to display them.

Do not regenerate into old folders. Generated projects are immutable records.

## Not Active Yet

Future stages are named in `placeholders.py`, but they are not run by
`run_placer_pipeline()`. They stay placeholders until the previous slice is
tested and accepted.

Next intended slices:

```text
Component Placer -> Placement Validator
Beautifier -> Beautifier Validator
Wire Planner -> Wire Maker
Terminal Placer -> Terminal Validator
Value Editor -> Value Validator
Final Validator -> Output
```
