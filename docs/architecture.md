# Architecture

The project is split into four independent layers.

## 1. Planner layer

The planner converts free-form user text into CircuitIR JSON. It may be GPT, Gemini, a local LLM, or any other model. The core generator must not depend on a particular model.

Input example:

```text
Make a voltage divider with 10k and 5k from VCC to GND and output at the middle.
```

Output: valid CircuitIR JSON matching `schemas/circuit_ir.schema.json`.

## 2. Validator layer

The validator checks CircuitIR before generation.

Responsibilities:

- schema validation
- duplicate component refs
- illegal net names
- unsupported components
- missing required values
- invalid or unsupported pin names
- topology sanity checks
- generation-readiness checks based on `knowledge/component_db.json`

The validator outputs `schemas/validation_report.schema.json`.

## 3. Generator layer

The generator is deterministic Python code. It consumes validated CircuitIR and emits a `.pdsprj` file.

Early strategy:

- use known-good Proteus 8.13 templates
- unpack `.pdsprj`
- build/update `ROOT.DSN` visual/topology data
- build/update `ROOT.CDB` component metadata
- copy `PROJECT.XML` and `SCRIPTS/PWRRAILS.DAT` from template, with optional timestamp updates later
- repack as `.pdsprj`

Initial emitted output domain: exact clean single-sheet template recipes. The first composition milestone is the structured AND reference circuit after D05-based validation.

### Component placer pipeline

The removal-only component placer now runs through the deterministic pipeline
used by the next native component route:

1. User input/CircuitIR validation.
2. Component placer.
3. Component packet validator.
4. Value changer.
5. Wiring planner.
6. Beautifier.
7. Final binary emission.

The current component placer keeps the accepted donor-packet emission path. It
does not synthesize terminals, wires, or cloned components. `SWITCH` and
`POT-HG` still request one extra donor packet, hide that dummy packet using the
accepted large relative offset, and record it in the manifest as
`hidden_dummy_controls`.

Each generated component-placement project writes a sidecar manifest:

```text
<output>.pdsprj.manifest.json
```

The manifest includes:

- `validation_reports`
- `value_plan`
- `wiring_plan`
- `layout_plan`
- `hidden_dummy_controls`

The value changer currently parses and validates supported value requests for
`RESISTOR`, `CAP`, `CAP-ELEC`, `REALIND`, `POT-HG`, `VSOURCE`, `CSOURCE`,
`VSINE`, and `VPULSE`. Binary DSN/CDB mutation is intentionally guarded until
family-specific patch rules are proven. The wiring planner emits net intent only
and never emits Proteus wire records.

## 4. Feedback / knowledge layer

Human/Proteus test results are recorded using `schemas/test_result.schema.json` and appended to `knowledge/test_results.jsonl`.

Confirmed findings are promoted into:

- `knowledge/rules.json`
- `knowledge/authority_model.json`
- `knowledge/component_db.json`
- `knowledge/open_questions.json`

## Current maturity level

The repo now contains a deterministic CLI, CircuitIR parsing and readiness validation, clean fixture provenance checks, exact-template generation, semantic project comparison, and result ingestion. Binary composition of rails/ICs remains intentionally blocked until its clean Proteus 8.13 oracle is available.
