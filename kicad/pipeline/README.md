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
