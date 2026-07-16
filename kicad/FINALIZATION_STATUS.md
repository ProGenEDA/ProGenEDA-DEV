# KiCad Schematic And PCB Finalization Status

Date: 2026-07-11

This is the current handoff for the integrated KiCad generator inside the
`memory/kicad` folder.

The schematic pipeline is finalized for its current catalogue. A bounded,
source-backed native PCB stage is now integrated and release-tested. See
`kicad/pcb/README.md` for its exact support envelope and evidence.

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
-> optional physical PCB compiler / placer / two-layer router
-> hosted PCB parser / validator
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

Each completed project emits two archives plus an optional direct PCB artifact:

- user project zip: openable KiCad project/schematic and accepted PCB files;
- internal bundle zip: main input JSON, every generated stage JSON, selected
  and rejected arrangement/routing variants, manifests, validator reports, and
  metadata keyed by the generated serial;
- direct user PCB: emitted only when hosted PCB validation passes.

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

## Current PCB Evidence

The accepted current PCB corpus run is:

```text
progen_kicad_executable_run_2026_07_11_174321_pcb_600_combination_v4
```

It completed 600/600 canonical combination-mode schematics. PCB results were
495 accepted, 67 complexity-limited, and 38 routing-limited. No rejected board
was copied into a user project.

The external KiCad 10.0.4 release oracle is:

```text
pcb_cli_oracle_run_2026_07_11_185217_pcb_600_combination_v4
```

All 495 accepted boards passed KiCad DRC with zero violations and zero
unconnected items. Hosted generation and validation remain independent of
KiCad installation; CLI is external evidence only.

## Remaining Work

The schematic generator is ready to move toward a small KiCad PCB slice after
one final optional sweep:

- rerun the 600 combination batch after the terminal-spacing change if updated
  visual evidence is required;
- regenerate the seven demo variations if the user wants the new 10.16 mm
  terminal spacing visible in demo files;
- add PDF/SVG preview export only when a hosted preview path is needed.

Remaining work is expansion, not completion of the current MVP slice:

- add audited footprint families beyond the committed 34-record source pack;
- improve compact placement and routing for the 38 routing-limited corpus cases;
- raise the explicit 40-component/40-multinet bounds only with new evidence;
- add zones, differential-pair/length constraints, thermal rules, and broader
  manufacturing profiles before calling the PCB stage universal production
  layout.
