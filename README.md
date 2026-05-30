# Proteus Native Project Generator Memory

This repository is the permanent project memory for building a lawful Proteus project-file generation workflow based on user-created test projects.

Current target:

- Proteus 8.13 first
- Native `.pdsprj` container creation/editing
- No modification of Proteus executables
- No license circumvention
- Generator input language: CircuitIR JSON
- Current generated domain: V9 terminal-based resistor graphs from E001
- Resistor generator status: locked as main for the current scope
- Capacitor status: temporary V5 cap3 diagnostics generated; waiting on ordered Proteus test before promotion
- Current power/ground support: one donor-derived `$TERPOWER -> $TEROUTPUT(V0)` bridge feeds powered `V0` input terminals; `G0` right endpoints become `$TERGROUND` with the normal short-wire-to-pin method
- Current resistor visual support: horizontal and 90-degree vertical records through `visual.orientation_hint`; `layout.visual_wires` is parsed but skipped in production until a safe donor is validated

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

## Important directories

```text
knowledge/   confirmed rules, component database, open questions, test results
docs/        architecture, file model, validator/generator design
schemas/     JSON schemas for CircuitIR and feedback
prompts/     prompts for converting natural language into CircuitIR
experiments/ experiment protocols and phase notes
fixtures/    clean Proteus fixtures and donors when mirrored locally
src/         deterministic Python package in the active generator repo
```
