# Proteus Native Project Generator Memory

This repository is the permanent project memory for building a lawful Proteus project-file generation workflow based on user-created test projects.

Current target:

- Proteus 8.13 first
- Native `.pdsprj` container creation/editing
- No modification of Proteus executables
- No license circumvention
- Generator input language: CircuitIR JSON
- Initial generated domain: exact clean single-sheet template recipes
- First pending composition milestone: one quad `74HC08` package with passive terminal/wire rails

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
proteusgen compare out\single_r1.pdsprj path\to\resaved.pdsprj
proteusgen record-result out\single_r1.result-template.json
python -m unittest discover -s tests -v
```

Run the CLI from this repository checkout. When invoking an installed package elsewhere, set `PROTEUSGEN_REPO_ROOT` to this checkout so it can load committed clean fixtures and knowledge files.

`examples/and_reference_pending_d05.json` is the acceptance circuit specification. It is intentionally rejected for generation until a clean Proteus 8.13 D05 oracle establishes safe terminal, rail, junction, and composed-IC rendering.

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
