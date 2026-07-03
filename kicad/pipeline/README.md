# KiCad Pipeline

This package is being built incrementally.

## Active Slice

Current proven flow:

```text
CircuitIR JSON -> Placement Input Validator -> Component Placer -> Placement Validator -> Arrangement Decider -> Beautifier -> Wire Planner -> KiCad Wire Maker -> KiCad project
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
- `kicad_wire_maker.make_kicad_wires(circuit, placement, wire_plan)`
  consumes pure JSON route output plus source-backed KiCad symbol pin geometry
  and emits real KiCad wire/junction objects in strict wire mode. Terminal or
  combination modes may emit local-label terminal objects through the terminal
  stage contract.

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

## Arrangement, Beautifier, Wire Planner, And Wire Maker

The post-placer stages remain independent:

- `arrangement_decider.decide_arrangement(placement, circuit)`
  emits a coordinate-plan JSON using topology depth, barycenter ordering,
  power/ground placement, clock detection, and density warnings.
- `beautifier.apply_coordinate_edits(placement, coordinate_plan)`
  applies only coordinate edits and returns a new placement JSON object.
- `wire_planner.plan_wire_routes(placement, circuit)`
  emits route-plan JSON for drawing backends and honors `routing_mode`.
- `terminal_placer.place_terminals(placement, circuit)`
  owns terminal/local-label connectivity plans.
- `kicad_wire_maker.py`
  is the first EDA-specific drawing backend. It does not plan routes. It
  resolves KiCad symbol pin/body geometry into `routing_inputs/`, feeds that
  pure JSON to the wire planner, draws actual wire/junction S-expressions in
  strict wire mode, and records unresolved pin aliases, partial-wire nets,
  unroutable nets, geometry validation, and strict-wire connectivity validation
  in each manifest.

`wire_planner.py` is deliberately pure math/JSON. It does not know about KiCad
S-expressions or Proteus files.

`routing_mode` is part of the final JSON and stage config:

- `wire`: every compiled net endpoint must be connected by the physical
  wire/junction/pin graph. Local labels are forbidden. Unroutable nets are
  reported as failures.
- `terminal`: local labels/terminal stubs are allowed and are owned by
  `terminal_placer.py`.
- `combination`: explicit mixed routing may use both wires and terminal plans.

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

The stage reports use bounded route-planning settings for batch evidence. In
strict `wire` mode, the planner must not emit local labels. If some branches of
a net are physically routed but one or more endpoints still fail, the net is
marked `partial_wire`; if no physical branch can be routed, the net is marked
`unroutable`. The KiCad wire maker draws available physical routes and records
both states as strict-wire validation failures. Terminal and combination modes
may use terminal/local-label strategies through the terminal stage contract.

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

Generate KiCad placement projects directly from connected final JSON with:

```text
python -m kicad.pipeline.final_circuit_builder --project-run-from-final-json kicad/examples/final_json_run_2026_07_02_132530_t01_t10_connected_v3/final_json --examples-root kicad/examples --label t01_t10_connected_projects_v1
```

Current generated run:

```text
kicad/examples/final_json_project_run_2026_07_02_133420_t01_t10_connected_projects_v1/
```

That run has 10 KiCad project folders generated from final JSON and static
quality passed 10/10. They are placement schematics with real embedded symbols;
the connected final JSON is preserved for wiring evidence.

Generate KiCad wired projects directly from connected final JSON with:

```text
python -m kicad.pipeline.kicad_wire_maker kicad/examples/final_json_run_2026_07_02_132530_t01_t10_connected_v3/final_json --examples-root kicad/examples --label t01_t10_connected_wired_v9_reserved_pin_router
```

Current generated wired run:

```text
kicad/examples/final_json_wired_project_run_2026_07_02_171521_t01_t10_connected_wired_v9_reserved_pin_router/
```

That run has 10 KiCad project folders with real embedded symbols plus KiCad
wire, label, and junction objects. Static schematic quality passed 10/10,
KiCad netlist export passed 10/10, and strict geometry validation passed 10/10
with 0 violations. It contains 430 components, 442 symbol instances, 360 wire
objects, and 1128 labels. The remaining 18 unresolved pins are recorded model
gaps: T07 has two artificial `LM358.BIAS` endpoints, and T08 needs a better LED
array/DIP-common symbol model. ERC quality currently passes 5/10, so this is
geometry-clean routing evidence, not final electrical acceptance.

After the 2026-07-03 routing-mode split, any run with local labels should be
treated as terminal/combination evidence, not strict `wire` mode acceptance.

The first strict wire-geometry validation run is:

```text
kicad/examples/final_json_wired_project_run_2026_07_02_164836_t01_t10_connected_wired_v5_geometry_rules/
```

That run adds hard checks that wires must not cross/touch other nets and must
not touch component bodies except at intended pins. Result: static schematic
quality passed 10/10, KiCad netlist export passed 10/10, but ERC quality passed
only 1/10 and geometry validation passed 0/10. Treat it as failure evidence for
the old router, not as accepted final wiring.

## Not Active Yet

Future stages are named in `placeholders.py`, but they are not run by
`run_placer_pipeline()`. They stay placeholders until the previous slice is
tested and accepted. `terminal_placer.py` now exists as the KiCad local-label
foundation, but a full terminal validator and accepted terminal path are still
future work.

Next intended slices:

```text
Component Placer -> Placement Validator
Beautifier -> Beautifier Validator
Wire Planner -> KiCad Wire Maker
Terminal Placer -> Terminal Validator
Value Editor -> Value Validator
Final Validator -> Output
```
