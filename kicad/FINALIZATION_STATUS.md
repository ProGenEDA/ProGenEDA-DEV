# KiCad Schematic Finalization Status

Date: 2026-07-10

This is the current handoff for the KiCad schematic generator inside the
`memory/kicad` folder.

## Current Pipeline

The active schematic path is:

```text
main JSON
-> input_json_validator_fixer
-> component placer
-> placement validator
-> arrangement decider
-> beautifier
-> wire planner / terminal placer / combination policy
-> KiCad wire maker
-> value editor
-> value validator
-> hosted expected-net validator
-> final validator
-> output packager
```

The single executable entry point is:

```bash
PYTHONPATH=. python -m kicad.pipeline.progen_kicad_executable run path/to/final_json --routing-mode combination
```

The default production direction is `combination`: route ordinary local nets
with wires, force power/ground and high-fanout/unresolved nets to terminals,
then validate against the expected netlist.

## Output Contract

Each completed project emits two artifacts:

- user project zip: only the openable KiCad project/schematic files;
- internal bundle zip: main input JSON, every generated stage JSON, selected
  and rejected arrangement/routing variants, manifests, validator reports, and
  metadata keyed by the generated serial.

The output packager owns this boundary:

```text
kicad/pipeline/output_packager.py
```

## Validation Contract

The current validator stack runs without requiring KiCad CLI:

1. file validity
2. component/reference/value checks
3. pin existence checks against source-backed KiCad symbol geometry
4. hosted `.kicad_sch` wire/junction/pin/label graph extraction
5. expected-net comparison against main JSON
6. optional ERC when `kicad-cli` is available
7. wire geometry and component-body overlap checks
8. final `final_validation_report.json`

The hosted netlist validator is:

```text
kicad/pipeline/kicad_netlist_validator.py
```

It parses generated KiCad S-expressions directly and compares actual electrical
connectivity with expected CircuitIR nets. It rejects missing pins, missing
members, merged nets, accidental power/ground shorts, floating expected pins,
and physical pin conflicts. KiCad ERC is useful extra evidence, but it is not
the authority for semantic net correctness.

## Terminal Spacing Rule

Terminal and combination schematics use KiCad local-label terminals. The writer
now places a terminal label 10.16 mm away from the resolved KiCad pin when that
short stub is safe.

The writer rejects a terminal stub if it would:

- cross or touch a component body except at the intended pin;
- touch a protected pin belonging to another net;
- hard-contact another net's wire segment;
- collide with an existing label point owned by a different net.

If no safe offset exists, the writer keeps the label pin-local instead of
drawing an unsafe stub. This keeps validation strict: prettier terminal spacing
cannot create a false electrical connection.

Implementation:

```text
kicad/pipeline/kicad_wire_maker.py
```

Tests:

```bash
PYTHONPATH=. python -m unittest kicad.tests.test_kicad_wire_maker -v
```

## Current Accepted Evidence

The compact evidence index is:

```text
kicad/examples/EVIDENCE_INDEX.md
```

Accepted schematic evidence:

- `progen_kicad_executable_run_2026_07_06_025855_executable_600_combination_v6`
  - 600/600 combination projects passed final validation.
  - Zero local-netlist failures, merged nets, power/ground shorts, geometry
    violations, component body overlaps, unresolved pins, unrouted nets, and
    partial wire nets.
- `progen_kicad_executable_run_2026_07_06_031455_executable_600_terminal_v1`
  - 600/600 terminal-only projects passed the same validator stack.
- `progen_kicad_executable_run_2026_07_10_130324_variation_100x3_v1_projects`
  - 100 random imported circuits x 3 variations passed as 300/300
    combination projects.
- `progen_kicad_executable_run_2026_07_10_133147_demo7_3variations_v1_projects`
  - 7 curated demo circuits x 3 variations passed as 21/21 combination
    projects.

Accepted source JSON:

- `final_json_run_2026_07_06_020659_main_json_catalog_600_combination_v2`
- `final_json_run_2026_07_06_020648_complex_500_from_node_spec_v2`
- `final_json_run_2026_07_10_133400_demo7_curated_source_v1`
- `final_json_variation_source_run_2026_07_10_130323_variation_100x3_v1_source`
- `final_json_variation_source_run_2026_07_10_133146_demo7_3variations_v1_source`

## Supported Components

The current placement catalog contains 163 normalized component kinds mapped to
real KiCad symbols or documented substitutes.

Source of truth:

```text
kicad/pipeline/placement_catalog.py
kicad/pipeline/SUPPORTED_COMPONENTS.md
kicad/source_pack/kicad_symbol_subset_v10_0_4.json
```

Future component additions should be made in the catalog, source-pack subset,
input fixer rules, pin aliases, tests, and evidence manifests together. Do not
add a component by only making the placer accept its name.

## Example Storage Policy

`kicad/examples` is 4.7 GB locally because it includes many generated evidence
runs. These are useful records, but they should not all be committed as normal
source files.

Policy:

- source code, tests, schemas, docs, compact run manifests, and curated small
  fixtures belong in Git;
- bulky generated project packs belong in the internal bundle/database path or
  an explicit artifact store;
- generated run folders are immutable once tested;
- awkward historical folder names should be documented, not renamed, after they
  become part of evidence.

The examples-specific ignore file prevents future generated project packs from
flooding source control while keeping compact summaries tracked.

## Remaining Schematic Work

The schematic generator is ready to move toward a small KiCad PCB slice after
one final optional sweep:

- rerun the 600 combination batch after the terminal-spacing change if updated
  visual evidence is required;
- regenerate the seven demo variations if the user wants the new 10.16 mm
  terminal spacing visible in demo files;
- add PDF/SVG preview export only when a hosted preview path is needed.

The main remaining KiCad work is PCB, not schematic connectivity.

Recommended PCB first slice:

```text
main JSON + validated schematic
-> footprint selector
-> board outline decider
-> footprint placer
-> ratsnest/net import validator
-> simple two-layer router or terminal/export placeholder
-> DRC/final PCB report
```

Start PCB with a small board, not the 600-circuit corpus.
