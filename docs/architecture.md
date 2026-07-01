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

### Canonical Progen EDA pipeline

The authoritative end-to-end order and implementation-status matrix are in
[`progen_eda_canonical_pipeline.md`](progen_eda_canonical_pipeline.md). It
supersedes older experimental stage orders.

### Current component-placer implementation

The removal-only component placer now runs through the deterministic pipeline
used by the next native component route:

1. User input/CircuitIR validation.
2. Component selection and placement.
3. Component packet and placement validation.
4. Beautification and beautifier validation.
5. Route-specific experimental stages.

The current component placer keeps the accepted donor-packet emission path. It
does not synthesize terminals, wires, or cloned components. `SWITCH` and
`POT-HG` use exactly the requested packet count and are beautified through
their proven linked coordinate plans.

### Replaceable placer contract

The component placer is an interchangeable producer. Removal from a mega
donor is the current implementation, not an architectural requirement. A
future byte-forming placer may add components to an empty sheet without
changing beautification, terminal placement, wiring, value editing, or final
validation if it emits the same placed-design contract.

That contract must contain:

- the generated backend project;
- ordered component identity, family, reference, and complete native packet;
- body bounds and transform/orientation;
- normalized pin descriptors: number, name, logical role, electrical type,
  connection coordinate, and backend record/link identity;
- backend/family profile IDs needed for safe mutation;
- explicit capabilities and unsupported families.

Downstream stages must not depend on:

- one giant donor filename or donor slot;
- fixed coordinates inherited from a template;
- globally hardcoded component IDs;
- the removal-only placer’s incidental object order;
- a value token or wire position belonging to one old project.

The current implementation is only partially decoupled. The packet beautifier
and terminal placer already accept ordered selected packets rather than a
specific mega-donor filename, but they still rely on Proteus family-specific
packet parsers and donor-derived terminal/wire profiles. The value editor
still supports only proven same-length property mutations. Replacing the
placer today is therefore feasible through an adapter, but not yet a zero-code
swap. The required cleanup is to formalize the placed-design/pin contract and
make every downstream stage consume it instead of private placer records.

For ICs, pin number and meaning must come from backend symbol/device metadata
or an accepted donor/library parser and be normalized into the pin descriptor.
Reset, clock, input, output, enable, and supply roles must never be guessed
from visual position alone. Proteus can source this from accepted DSN/CDB
device evidence; KiCad should source it from symbol-library pin metadata.

Logical CircuitIR and stage contracts should remain backend-neutral. Proteus,
KiCad, PSpice, and Altium details belong in backend profiles and emitters so
the same high-level architecture can scale to 200+ component families.

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
- `validation_reports.generated_output_validator`

The value changer now applies the first proven binary mutation path:
same-length selected-packet value-token edits, mirrored into matching CDB
property rows when the selected row contains the old value token. Current
proven families are `RESISTOR`, `CAP`, `CAP-ELEC`, `REALIND`, `POT-HG`,
`VSOURCE`, and `CSOURCE`. `VSINE` and `VPULSE` remain blocked for value
mutation until their property rows are decoded. The wiring planner emits net
intent only and never emits Proteus wire records.

The generic all-family bounding-box terminal experiment was rejected. Terminal
attachment now proceeds family by family in the single
`component_terminal_placer.py` module. `RESISTOR/v3` is the first accepted
handler and uses matched pin-link suffixes plus donor-derived short wires.

Every stage must eventually provide both a direct stage-output validator and a
cumulative validator covering all accepted earlier stages. User-specification,
information-completeness, and final whole-project validators surround that
technical chain.

## 4. Feedback / knowledge layer

Human/Proteus test results are recorded using `schemas/test_result.schema.json` and appended to `knowledge/test_results.jsonl`.

Confirmed findings are promoted into:

- `knowledge/rules.json`
- `knowledge/authority_model.json`
- `knowledge/component_db.json`
- `knowledge/open_questions.json`

## Current maturity level

The repository contains a deterministic CLI, CircuitIR parsing and readiness
validation, fixture provenance checks, locked legacy circuit generators,
removal-only mega-donor component placement, family-specific coordinate
mutation, semantic project comparison, and result ingestion. Value editing is
lightly tested. Focused terminal attachment is accepted for RESISTOR, CAP,
REALIND, CAP-ELEC, VSOURCE, and CSOURCE; the unified mixed short-wire route
remains experimental. Formal placed-design and normalized-pin contracts are
the next decoupling milestone after terminal placement.
