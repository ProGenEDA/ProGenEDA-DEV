# Agent Instructions

This repository stores the working memory for a Proteus `.pdsprj` generator project.

## Mission

Build a Python-based system that accepts a strict CircuitIR JSON circuit description and emits a Proteus 8.x `.pdsprj` file.

The planner is outside the core generator. Any AI model may later convert user text into CircuitIR. The generator and validator must be deterministic.

## Hard boundaries

- Do not modify Proteus executables.
- Do not bypass licensing.
- Do not depend on GUI automation for the main Route A generator.
- Use only user-created test projects and public example project files as research/corpus material.
- Keep generated project files compatible with the observed `.pdsprj` container structure.

## Current known file model

For Proteus 8.13 `.pdsprj`:

- The outer `.pdsprj` is a ZIP-style container.
- Required internal files observed: `PROJECT.XML`, `ROOT.DSN`, `ROOT.CDB`, `SCRIPTS/PWRRAILS.DAT`.
- `ROOT.DSN` controls visual object existence, terminal labels, visible wires, and topology.
- `ROOT.CDB` controls resistor values and reference names for existing resistors.
- `ROOT.CDB` must exist; removing it causes fatal Proteus/ISIS failure in tests.
- `SCRIPTS/PWRRAILS.DAT` has remained unchanged in visible terminal/resistor experiments.

## Implementation language

Use Python 3.11+.

Recommended package modules:

```text
src/proteusgen/extractor.py
src/proteusgen/analyzer.py
src/proteusgen/validator.py
src/proteusgen/generator.py
src/proteusgen/packer.py
src/proteusgen/circuit_ir.py
src/proteusgen/knowledge.py
```

Recommended libraries:

```text
pydantic
jsonschema
typer
rich
networkx
construct
pytest
```

## Input language

Use CircuitIR JSON. Do not make the generator parse free-form English.

The planner prompt in `prompts/planner_prompt.md` is responsible for turning natural language into CircuitIR.

## Current generator target

The CLI and CircuitIR contract exist. Enable output conservatively:

- Production generation is restricted to whole clean templates with explicit recipes until composed-object transformations are validated.
- The first composed-output acceptance case is one quad `74HC08` package with two resistor rails and labelled input terminals, specified in `examples/and_reference_pending_d05.json`.
- Do not enable the AND acceptance case until the clean Proteus 8.13 D05 oracle has been supplied and a generated project passes open/save comparison.
- Use terminal/net-label topology where safe, but do not assume labelled terminals replace visible wire/junction records required by the reference circuit.

## Development style

- Update `knowledge/test_results.jsonl` after every test batch.
- Promote repeatable findings into `knowledge/rules.json`.
- Keep uncertain items in `knowledge/open_questions.json`.
- Update `docs/proteus_file_model.md` when evidence changes.
- Avoid speculative generator logic unless marked experimental.
