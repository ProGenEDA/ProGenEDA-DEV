# Proteus Native Project Generator Memory

This repository is the permanent project memory for building a lawful Proteus project-file generation workflow based on user-created test projects.

Current target:

- Proteus 8.13 first
- Native `.pdsprj` container creation/editing
- No modification of Proteus executables
- No license circumvention
- Generator input language: CircuitIR JSON
- Current generated domain: locked V9 terminal-based resistor graphs from E001, locked mixed resistor/capacitor/inductor group-based graphs, and locked source-driven R/C/L graphs using DC voltage, DC current, or one AC voltage source
- Resistor generator status: accepted as main for the current scope
- Capacitor status: terminal-attached capacitor records are accepted inside the locked mixed passive generator; standalone capacitor-only promotion remains in temporary V13 testing
- Inductor status: standalone inductor generation remains temporary; mixed R/C/L generation is locked for the accepted group-based scope through the 6-component, corrected 21-rule, and 15 topology packs
- Current power/ground support: one donor-derived `$TERPOWER -> $TEROUTPUT(V0)` bridge feeds powered `V0` input terminals; `G0` right endpoints become `$TERGROUND`
- Current resistor visual support: horizontal and 90-degree vertical records through `visual.orientation_hint`; `layout.visual_wires` is parsed but skipped in production until a safe donor is validated
- Experimental layout support: topology-aware `beautify`, exact `manual`, and byte-compatible `legacy` strategies; `legacy` remains the default until the representative Proteus pack is accepted
- Pending later composition milestone: one quad `74HC08` package with passive terminal/wire rails

The repo is designed so Codex or another coding agent can read the knowledge files, schemas, and docs to build the validator/generator.

## Current architecture

```text
User prompt
  -> planner prompt / external AI
  -> CircuitIR JSON
  -> validator
  -> Proteus native generator
  -> .pdsprj
  -> Proteus test
  -> feedback JSON
  -> knowledge update
```

## CLI

Install in editable mode and inspect or generate from strict JSON:

```powershell
python -m pip install -e .
proteusgen fixtures
proteusgen validate examples\single_resistor_vcc_gnd.json
proteusgen generate examples\single_resistor_vcc_gnd.json --output out\single_r1.pdsprj
proteusgen generate-resistors examples\resistor_v9_power_ground.json --outdir out\single_r_power_ground
proteusgen generate-mixed-passives path\to\mixed_passive.json --outdir out\mixed_passive
proteusgen generate-mixed-rcl path\to\mixed_rcl.json --outdir out\mixed_rcl
proteusgen generate-source-driven examples\source_driven_default_dcv.json --outdir out\source_driven
proteusgen plan-layout path\to\circuit.json --layout-strategy beautify --output out\layout_plan.json
proteusgen generate-mixed-rcl path\to\mixed_rcl.json --outdir out\beautified --layout-strategy beautify
python generate_from_json.py --input examples\resistor_v9_power_ground.json --outdir out\single_r_power_ground
proteusgen compare out\single_r1.pdsprj path\to\resaved.pdsprj
proteusgen record-result out\single_r1.result-template.json
python -m unittest discover -s tests -v
```

Run the CLI from this repository checkout. When invoking an installed package elsewhere, set `PROTEUSGEN_REPO_ROOT` to this checkout so it can load committed clean fixtures and knowledge files.

The V9 resistor generator reads `proteus-circuit-ir/v0.1` JSON. See `docs/resistor_json_input.md` and `schemas/resistor_circuit_ir_v0_1.schema.json`.

The mixed resistor/capacitor generator reads `proteus-mixed-passive-ir/v0.1` JSON. It uses the same two-character `V0`/`G0` power-ground convention and the locked safe-spacing rules.

The mixed R/C/L generator reads `mixed-rcl-circuit-ir/v0.1` JSON. See `docs/mixed_rcl_json_input.md`. Its current locked input shape is group-based: each group is one accepted donor-derived `RCL`, `RC`, `LC`, `RL`, or `C` block with two-character terminal labels.

The source-driven generator reads `source-driven-rcl-circuit-ir/v0.1`. It supports one or more DC voltage/current sources and one AC voltage source. AC current is not supported. Source circuits use ordinary two-character source-net terminals and do not add the passive `V0` power bridge or `G0` ground terminals.

The experimental deterministic beautifier is documented in `docs/beautifier.md`. It plans coordinates before binary emission and only translates complete donor-derived records. It does not post-process projects or create arbitrary wires and junctions.

The temporary inductor work-in-progress lives under `tools/proteus_generation/2026-06-01/inductor_temp_from_premature_main`.

`examples/and_reference_pending_d05.json` is the later AND acceptance circuit specification. It remains blocked for production until a clean Proteus 8.13 D05 oracle establishes safe terminal, rail, junction, and composed-IC rendering.

## Important directories

```text
knowledge/   confirmed rules, component database, open questions, test results
docs/        architecture, file model, validator/generator design
schemas/     JSON schemas for CircuitIR and feedback
prompts/     prompts for converting natural language into CircuitIR
experiments/ experiment protocols and phase notes
fixtures/    small clean user-created Proteus projects with hashes/provenance
examples/    CircuitIR inputs and the pending AND acceptance circuit
src/         deterministic Python package and CLI
tests/       automated contract, fixture and deterministic-output checks
```
