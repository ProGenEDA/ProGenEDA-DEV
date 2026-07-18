# KiCad Pipeline

This package was built incrementally and is now the active KiCad production
pipeline. Historical planner and placer notes remain below as engineering
record; the executable entry point runs the complete validated path.

## Codex 5.6 Active Pipeline

Codex 5.6 assembled the independent modules in this directory into a real
backend rather than a diagram of intended stages. It built the deterministic
main-JSON fixer, canonical placer, movement-first arrangement/beautifier loop,
routing and terminal contracts, native KiCad writer, value tools, source-backed
expected-net validator, final validator, PCB handoff, output packager, portable
launcher, and large-corpus evidence.

That is the central 5.6 advantage over the earlier 5.5-era work: each stage is
still replaceable and testable alone, but the normal command now executes the
whole chain, retains accepted and rejected variants, and refuses to package a
circuit with a blocking electrical or geometry failure. The 400-circuit
qualification and its shared pin/body-clearance repair are the clearest proof
of that step forward. See [`../qualification/RESULTS_2026_07_17.md`](../qualification/RESULTS_2026_07_17.md).

## Active Slice

Current proven flow:

```text
CircuitIR JSON -> Placement Input Validator -> Component Placer -> Placement Validator -> Arrangement Decider -> Beautifier -> Wire Planner/Terminal Placer -> KiCad Wire Maker -> Value Editor -> Value Validator -> Final Validator -> Output Packager -> KiCad project + internal bundle
```

The active stages are independent:

- `placement_input_validator.validate_placement_input(circuit)`
  checks component kinds and pin numbers against
  `kicad.generator.kicad_json_to_project.KIND_SPECS`.
- `input_json_validator_fixer.validate_and_fix_main_json(circuit)`
  repairs loose main JSON into canonical CircuitIR. Any invented/repaired net is
  named `GUESS_TERMINAL_*` and forced into terminal handling.
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
- `value_editor.apply_value_edits(circuit, schematic_path)`
  applies main JSON component values to generated KiCad schematic symbols.
- `value_validator.validate_component_values(circuit, schematic_path)`
  reparses the generated schematic and validates reference/value correctness.
- `final_validator.validate_final_project(circuit, project_dir)`
  aggregates file, value, pin, expected-net, optional ERC, geometry, body
  overlap, and routing-contract evidence into `final_validation_report.json`.
- `output_packager.package_generated_project(...)`
  emits the user-downloadable project zip and the internal-only metadata bundle.
- `progen_kicad_executable.py`
  is the single command wrapper: it validates/fixes main JSON, runs generation,
  and writes the two output artifacts for each project. It also supports
  deterministic layout-variation batches.

This active placer slice does not require KiCad to be installed. It uses
embedded Python metadata from the repository:

- source-backed generator specs in `kicad.generator.kicad_json_to_project.KIND_SPECS`
- partial CircuitIR placement specs in `kicad.pipeline.placement_catalog`

The placement validator is intentionally narrow; it is one stage in the active
output validation stack:

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

The hosted final validator implements the deterministic portions without
requiring KiCad CLI. KiCad netlist export/ERC and preview export remain
external evidence paths when installed tooling is available. The internal bundle
keeps the full report history for database storage.

## Executable And Variation Commands

Main generation:

```bash
PYTHONPATH=. python -m kicad.pipeline.progen_kicad_executable run path/to/final_json --routing-mode combination
```

Deterministic variation generation:

```bash
PYTHONPATH=. python -m kicad.pipeline.progen_kicad_executable run-variations path/to/final_json --routing-mode combination --sample-count 100 --variations-per-circuit 3 --seed 20260710
```

`run-variations` samples `N*` new-500 corpus files by default, clones each
selected circuit, preserves the same connectivity, adds
`generation_variation`, and then runs the normal executable path. Variation
mode disables the combination wire-route cap for that generated batch only;
normal combination generation keeps the cap for speed.

Latest local evidence:

- 600/600 combination projects passed final validation and hosted local-netlist
  comparison with zero unresolved pins, zero merged nets, zero geometry
  violations, and zero final blocking failures.
- 600/600 terminal-only projects passed the same validator stack.
- 100 random new-500 circuits x 3 variations passed as 300/300 combination
  variation projects with zero local-netlist/geometry/final failures.
- 7 curated demo circuits x 3 variations passed as 21/21 combination variation
  projects with zero local-netlist/geometry/final failures.

## Arrangement, Beautifier, Wire Planner, And Wire Maker

The post-placer stages remain independent:

- `arrangement_decider.decide_arrangement(placement, circuit)`
  emits a coordinate-plan JSON using topology depth, barycenter ordering,
  power/ground placement, clock detection, and density warnings.
- `beautifier.apply_coordinate_edits(placement, coordinate_plan)`
  applies only coordinate edits and returns a new placement JSON object.
- `wire_planner.plan_wire_routes(placement, circuit)`
  emits route-plan JSON for drawing backends and honors `routing_mode`.
- `wire_planner.plan_partial_route_component_moves(placement, wire_plan)`
  emits a coordinate-plan JSON for failed partial routes. It moves only failed
  endpoint components toward their nearest already-wired same-net neighbor and
  leaves coordinate application to `beautifier.py`.
- `terminal_placer.place_terminals(placement, circuit)`
  owns terminal/local-label connectivity plans.
- `kicad_wire_maker.py`
  is the first EDA-specific drawing backend. It does not plan routes. It
  resolves KiCad symbol pin/body geometry into `routing_inputs/`, feeds that
  pure JSON to the wire planner, applies partial-route coordinate repair through
  the same beautifier contract when strict wire mode reports partial nets, draws
  actual wire/junction S-expressions, and records unresolved pin aliases,
  partial-wire nets, unroutable nets, geometry validation, and strict-wire
  connectivity validation in each manifest.
  In terminal and combination modes it emits KiCad local labels with a default
  10.16 mm pin-to-label offset where safe. Candidate terminal stubs are rejected
  if they cross component bodies, touch protected pins from another net, or
  hard-contact another net. If the local area is too dense, the writer keeps the
  label pin-local rather than drawing an unsafe visual stub.

`wire_planner.py` is deliberately pure math/JSON. It does not know about KiCad
S-expressions or Proteus files.

## Routing V2 Refactor

The extracted PDF plan is preserved at
`kicad/pipeline/ROUTING_REFACTOR_PLAN_SOURCE.md`.

The v2 routing implementation lives under `kicad/pipeline/routing/` and adds:

- permanent abstract catalogues in `kicad/pipeline/catelogues/`
- a mathematical `LiveRoutingState` as the only optimization scratchpad
- rotation-aware pin/body/keepout recomputation
- weighted graph pivot selection, cluster-growth beam search, Pareto pruning,
  branch pruning, and priority-aware legalization
- deep routing of the original, rotation-baseline, and top beam variants before
  selecting the final coordinate plan
- Hanan-grid lane anchors, rectilinear MST metadata, Manhattan A* fallback,
  indexed crossing counts, and tile-based crossing-density metrics
- a v0.2 routing orchestrator and validation report
- a Rust-core source boundary with the planned PyO3 JSON API; the Nix Rust
  toolchain is installed and the temp parity core is buildable, while Python
  remains authoritative for full routing until the Rust core proves parity
- stricter final KiCad wire validation and exact-pin path repair

Existing v0.1 planner contracts remain available for compatibility; v2 emits
the PDF's `coordinate_plan`, `routing_placement`, `wire_plan`,
`arrangement_selection`, metrics, warnings, and `validation_report` contract.

The combined `wire_planner.plan_wiring()` contract is movement-first:

```text
placement -> arrangement variant generator -> beautifier -> routeability score -> full-route selected placement
```

This means component coordinates are chosen before final route search. The
selector scores multiple moved placements with a fast routeability estimate and
uses parallel workers on larger designs. Future arrangement variations can keep
several high-scoring coordinate plans instead of only the best one.

`routing_mode` is part of the final JSON and stage config:

- `wire`: every compiled net endpoint must be connected by the physical
  wire/junction/pin graph. Local labels are forbidden. Unroutable nets are
  reported as failures. Wire-wire crossings are allowed; wires crossing
  component bodies are not.
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

Current exact strict-wire T10 evidence:

```text
kicad/examples/final_json_wired_project_run_2026_07_03_213416_t10_exact_strict_wire_repair_v1/
```

That run generated the 190-component near-limit T10 schematic with 554 resolved
routing pins, 1503 wire objects, 0 labels, 0 unresolved pins, 0 deferred nets,
0 unrouted nets, 0 partial-wire nets, 0 geometry violations, and strict physical
wire graph validation passed. KiCad netlist export also passed. KiCad ERC still
reports symbol electrical-type issues (`pin_to_pin` and `ground_pin_not_ground`),
so ERC cleanup remains a separate logical validation task.

The first strict wire-geometry validation run is:

```text
kicad/examples/final_json_wired_project_run_2026_07_02_164836_t01_t10_connected_wired_v5_geometry_rules/
```

That run added hard checks that wires must not cross/touch other nets and must
not touch component bodies except at intended pins. That older rule set is now
superseded: wire-wire crossings are allowed, while component-body contact and
missing physical endpoint connectivity remain hard blockers. Treat the run as
failure evidence for the old router, not as accepted final wiring.

## Historical Placer-Only Roadmap

The retained `run_placer_pipeline()` notes below describe the original
placer-only experiment path, not the production executable. The production
path above now runs terminal/combination logic, value validation, expected-net
validation, final validation, and output packaging. `placeholders.py` remains
useful for future extensions that are deliberately outside the current release
scope.

Original intended slices, retained as the architecture record:

```text
Component Placer -> Placement Validator
Beautifier -> Beautifier Validator
Wire Planner -> KiCad Wire Maker
Terminal Placer -> Terminal Validator
Value Editor -> Value Validator
Final Validator -> Output
```
