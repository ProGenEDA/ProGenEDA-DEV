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

The active Proteus route has moved away from synthesizing circuits from empty
projects. The production direction is now removal-only donor mutation:

- Start from a trusted donor or mega donor that already contains the needed
  components.
- Remove unneeded complete component packets and linked metadata.
- Do not clone, synthesize, or freehand component records in the production
  component placer.
- The component placer only places/selects components. It must not add
  terminals or wires.
- After placement the pipeline is: component packet validation, value changer,
  wiring-intent planner, beautifier, final binary emission.
- Value changing, terminal generation, and wiring are separate stages. Do not
  mix those responsibilities into the component placer.

The current active engineering focus is the component-packet beautifier. It is
strictly a coordinate/layout stage. Because coordinate fields vary by component
family, improve it family-by-family inside the shared implementation rather
than assuming one byte-edit method works for every component.

## Development style

- Update `knowledge/test_results.jsonl` after every test batch.
- Promote repeatable findings into `knowledge/rules.json`.
- Keep uncertain items in `knowledge/open_questions.json`.
- Update `docs/proteus_file_model.md` when evidence changes.
- Avoid speculative generator logic unless marked experimental.
- Every experiment must have or update a Markdown note explaining the purpose,
  generated files, what the user should inspect in Proteus, user feedback, and
  Codex observations/root cause.
- When the user reports results, update the experiment Markdown before moving
  to the next variant.
- Keep iteration history traceable: do not replace the tested `.py` behavior
  from scratch; copy/update the current baseline, then promote only after user
  acceptance.
