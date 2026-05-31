# Proteus Native Project Generator Memory

This repository is the permanent project memory for building a lawful Proteus project-file generation workflow based on user-created test projects.

Current target:

- Proteus 8.13 first
- Native `.pdsprj` container creation/editing
- No modification of Proteus executables
- No license circumvention
- Generator input language: CircuitIR JSON
- Current generated domain: locked V9 terminal-based resistor graphs from E001, locked mixed resistor/capacitor passive graphs, and locked scoped inductor graphs
- Resistor generator status: accepted as main for the current scope
- Capacitor status: terminal-attached capacitor records are accepted inside the locked mixed passive generator; standalone capacitor-only promotion remains in temporary V13 testing
- Inductor status: terminal-only one-to-three inductor generation is locked; single `V0` to `G0` inductor generation is locked through the donor04 object order
- Current power/ground support: one donor-derived `$TERPOWER -> $TEROUTPUT(V0)` bridge feeds powered `V0` input terminals; `G0` right endpoints become `$TERGROUND`
- Current resistor visual support: horizontal and 90-degree vertical records through `visual.orientation_hint`; `layout.visual_wires` is parsed but skipped in production until a safe donor is validated
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
proteusgen generate-inductors examples\inductor_locked_t02_single_power_ground.json --outdir out\single_l_power_ground
python generate_from_json.py --input examples\resistor_v9_power_ground.json --outdir out\single_r_power_ground
proteusgen compare out\single_r1.pdsprj path\to\resaved.pdsprj
proteusgen record-result out\single_r1.result-template.json
python -m unittest discover -s tests -v
```

Run the CLI from this repository checkout. When invoking an installed package elsewhere, set `PROTEUSGEN_REPO_ROOT` to this checkout so it can load committed clean fixtures and knowledge files.

The V9 resistor generator reads `proteus-circuit-ir/v0.1` JSON. See `docs/resistor_json_input.md` and `schemas/resistor_circuit_ir_v0_1.schema.json`.

The mixed resistor/capacitor generator reads `proteus-mixed-passive-ir/v0.1` JSON. It uses the same two-character `V0`/`G0` power-ground convention and the locked safe-spacing rules.

The inductor generator reads `proteus-inductor-ir/v0.1` JSON. See `docs/inductor_json_input.md` and `schemas/inductor_circuit_ir_v0_1.schema.json`.

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
