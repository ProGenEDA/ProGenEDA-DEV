# Progen

**A deterministic circuit compiler for native Proteus projects.**

Progen is an unusual engineering project: it learns the structure of
user-created Proteus 8.13 projects, turns those observations into explicit
binary rules, and then generates new `.pdsprj` files without modifying Proteus
or relying on UI automation.

The long-term target is straightforward to describe and difficult to build:

```text
natural-language circuit
  -> validated CircuitIR
  -> components
  -> values
  -> topology-aware layout
  -> wires or named terminals
  -> native Proteus project
  -> structural and simulation validation
```

What makes Progen interesting is its refusal to hide uncertainty. Every donor,
packet rule, failure, accepted workaround, validator, and Proteus result is
recorded in this repository so another engineer or coding agent can continue
from evidence rather than rediscovering the same binary traps.

## Current Focus

The active route is a removal-only component placer:

1. Select a trusted mega donor containing enough real components.
2. Keep complete component packets and remove the rest.
3. Preserve the accepted CDB/device skeleton.
4. Validate exact counts, references, models, IDs, and container structure.
5. Change coordinates only through a proven family-specific parser.

The current work is proving bare IC placement family by family before ICs are
combined with each other and with the already-tested passive, source, display,
control, transistor, diode, transformer, and analog families.

## What Already Exists

- Locked resistor, mixed-passive, mixed-RCL, and source-driven generators.
- Accepted combinational IC generation for `74HC00`, `74HC02`, `74HC04`,
  `74HC08`, `74HC32`, `74HC86`, and `74HC266`.
- A trusted mega-donor component placer supporting broad digital, analog,
  source, display, control, transistor, diode, and passive inventories.
- Family-specific coordinate mutation for accepted non-IC families.
- Exact-count `SWITCH` and `POT-HG` placement.
- Seven-segment donor composition with preserved D20 infrastructure.
- Deterministic value and wiring-intent plans in generation manifests.
- A generated-output validator that checks exact counts, CDB integrity,
  reference preservation, parser policy, and immutable infrastructure.
- A permanent evidence base in `knowledge/`, `docs/`, and `experiments/`.

## Current Pipeline

```text
User/CircuitIR validation
  -> donor selection
  -> component placer
  -> component/output validation
  -> value changer
  -> wiring-intent planner
  -> beautifier
  -> binary emission
```

Value mutation and final wire emission are still guarded until their
family-specific rules pass Proteus testing.

## Important Truths

- The component placer places bare components. It does not yet add wires,
  junctions, power terminals, or ordinary terminals.
- D20 is required seven-segment infrastructure, is not counted as a requested
  diode, and currently stays at its donor coordinates.
- The accepted resistor-heavy ceiling is `R91`.
- Full donor CDB preservation is currently safer than aggressive CDB pruning.
- Proteus 8.13 open/render/simulation testing remains the final authority.

The complete operational list is in
[Current Limits, Bridges, Costs, and Roadmap](docs/current_limitations_bridges_costs_and_roadmap.md).

## CLI

Install locally:

```powershell
python -m pip install -e .
```

Useful commands:

```powershell
proteusgen validate examples\single_resistor_vcc_gnd.json
proteusgen generate-resistors examples\resistor_v9_power_ground.json --outdir out\resistor
proteusgen generate-mixed-rcl path\to\mixed_rcl.json --outdir out\mixed_rcl
proteusgen generate-source-driven examples\source_driven_default_dcv.json --outdir out\source
proteusgen generate-ic-combinational path\to\logic.json --outdir out\logic
proteusgen plan-component-placement path\to\components.json --output out\plan.json
proteusgen generate-component-placement path\to\components.json --output out\components.pdsprj
proteusgen plan-layout path\to\circuit.json --layout-strategy beautify
python -m pytest tests -q
```

Set `PROTEUSGEN_REPO_ROOT` when invoking an installed package outside this
checkout so it can locate committed donors, fixtures, and knowledge files.

## Repository Map

```text
src/          deterministic generators, parsers, planners, and validators
tests/        regression and contract tests
knowledge/    accepted rules, component data, open questions, test results
docs/         architecture, binary findings, limits, and continuation memory
schemas/      CircuitIR and result contracts
prompts/      natural-language to CircuitIR guidance
fixtures/     small clean projects with provenance and hashes
experiments/  generated acceptance packs and their Markdown test records
proteus_ic/   IC registries and trusted donor corpus
```

## Development Rule

No binary guess becomes a feature because it looked plausible once.

A change is promoted only after:

1. byte-level donor comparison;
2. deterministic generation;
3. stage-specific validation;
4. cumulative regression validation;
5. Proteus open/render/simulation feedback;
6. permanent recording in the knowledge base.

That discipline is slower than blind byte patching and dramatically faster
than repeating the same crash months later.
