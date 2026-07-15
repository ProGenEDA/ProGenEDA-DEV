# Progen

**A deterministic circuit compiler for native Proteus and KiCad projects.**

Progen learns from user-created schematic projects, converts that evidence into
explicit binary and structural rules, and emits projects that open in the real
EDA application. The core generator is deterministic: an AI may translate
natural language into JSON, but it does not patch schematic binaries directly.

The project is deliberately evidence-driven. Donors, failed approaches,
accepted workarounds, binary observations, validators, and user Proteus results
are kept together so development can continue without rediscovering old
loader, CDB, model, and object-boundary failures.

## Project Status

Updated: **2026-06-29**

The active Proteus architecture is a **removal-only mega-donor component
pipeline**. It selects complete native component packets from trusted donors,
removes unrequested packets, preserves the accepted device/CDB skeleton, and
then applies independently validated post-placement stages.

```text
user text (outside deterministic core)
  -> CircuitIR / component-placement JSON
  -> user-input and readiness validation
  -> donor selection
  -> component packet placement
  -> component/output validation
  -> value mutation
  -> wiring-intent planning
  -> coordinate beautification
  -> terminal/wire stages
  -> final binary emission and validation
  -> Proteus open/render/simulation acceptance
```

Current milestone:

- component placement is working from the trusted mega donors;
- family-specific coordinate mutation is working for the accepted bare
  component families;
- the value changer has a conservative same-length DSN/CDB mutation path;
- the terminal placer can append all-family bidirectional terminal records
  with correct left/right orientation;
- real pin attachment and donor-derived short-wire emission are the next
  terminal milestone;
- final arbitrary wiring remains intentionally unpromoted.

## Why Removal-Only

Proteus `.pdsprj` files contain related object, property, model, ID, and device
metadata across `ROOT.DSN` and `ROOT.CDB`. Copying only a visible symbol or
inventing records from scratch repeatedly caused:

- `ISIS.DLL`, `VGDVC.DLL`, and `LXLCORE.DLL` failures;
- bad-object warnings;
- duplicate package and object references;
- missing simulation models;
- projects that opened but failed during netlist compilation.

The current route therefore keeps complete donor-native packets and mutates
only byte fields proven for that family.

## Proteus Capabilities

### Locked legacy generators

These routes predate the unified component placer and remain useful:

- resistor networks with power and ground;
- capacitor, inductor, RC, RL, LC, and RCL networks;
- DC voltage, DC current, and AC voltage source-driven passive circuits;
- bidirectional endpoint variants;
- combinational logic generation for `74HC00`, `74HC02`, `74HC04`, `74HC08`,
  `74HC32`, `74HC86`, and `74HC266`;
- Boolean AND/OR trees and mixed combinational/RCL circuits.

### Unified component placer inventory

The active mega-donor placer supports bare placement of:

**Passives and discrete devices**

`RESISTOR`, `CAP`, `CAP-ELEC`, `REALIND`, `DIODE`, `1N4007`, `1N4148`,
`1N4733A`, `1N6000B`, `40EPS08` (`IRDIODE` prompt alias), `BZX55C5V1`, `BZX79C5V1`,
`BZY88C`, `LED-RED`, `BRIDGE`, `FUSE`, `NPN`, `PNP`, `2N3904`, `2N4401`,
`NMOSFET`, `2N7000`, `BS170`, and `TRAN-2P2S`.

**Analog, timing, and controls**

`LM317T`, `LM741`, `OPAMP`, `NE555`, `POT-HG`, and `SWITCH`.

**Sources**

`VSOURCE`, `CSOURCE`, `VSINE`, and `VPULSE`.

**Displays**

`7SEG-COM-AN-BLUE` (`7SEGCOMA`) and `7SEG-COM-CAT-BLUE` (`7SEGCOMK`).

**IC packages**

`4027`, `4511`, `7447`, `7490`, `74HC00`, `74HC02`, `74HC04`, `74HC08`,
`74HC32`, `74HC74`, `74HC76`, `74HC85`, `74HC86`, `74HC151`, `74HC157`,
`74HC160`, `74HC174`, `74HC192`, `74HC266`, and `74HC283`.

Component aliases and the authoritative grouped list live in
[`proteus_ic/registry/mega_component_support_20260618.json`](proteus_ic/registry/mega_component_support_20260618.json).

Support here means a native packet can be selected and placed. It does not mean
every arbitrary combination is already wired or simulation-certified.

## Pipeline Stages

| Stage | Current state |
|---|---|
| Input validation | Implemented for CircuitIR and component-placement payloads |
| Donor selection | Implemented, including explicit donor selection |
| Component placement | Implemented through complete donor-packet removal |
| Packet/output validation | Implemented in generation manifests |
| Value changer | Experimental, same-length family-safe tokens only |
| Wiring planner | Implemented as logical intent; emits no Proteus wires |
| Beautifier | Implemented through family-registered coordinate parsers |
| Bidir terminal placer | Experimental all-family side-anchor stage |
| Short-wire pin attachment | Next active terminal task |
| Arbitrary binary wiring | Not promoted |
| Power/ground terminal layer | Planned after attached bidirs |
| Final whole-project validator | Partially implemented; still expanding |

### Value changer

Binary mutation is currently allowed for proven compact tokens in:

- `RESISTOR`
- `CAP`
- `CAP-ELEC`
- `REALIND`
- `POT-HG`
- `VSOURCE`
- `CSOURCE`

The mutation updates the selected DSN packet and a matching CDB property row
when present. Unsupported syntax fails before mutation. `VSINE` and `VPULSE`
value/property mutation remain blocked until their model fields are decoded.

### Beautifier

The component placer beautifier moves complete packets using coordinate fields
registered per family. Multi-symbol packages are allocated by measured packet
footprint rather than treated as one tiny IC rectangle.

Do not reintroduce broad integer scanning or guessed fixed offsets. Those
methods produced valid-looking files that crashed Proteus.

### Bidirectional terminals

The current terminal experiment:

- covers every selected user component family;
- owns generated terminal names;
- uses 180 degrees on the left and 0 degrees on the right;
- excludes D20 and display-final infrastructure;
- appends complete donor-derived `$TERBIDIR` records.

Its current policy is `bbox_side_anchor_no_wire`. This proves terminal record
construction and orientation, not electrical attachment. Accepted donors show
that some pins need a short `WIRE` record; that is the next implementation
step.

## Input Examples

Component-placement JSON:

```json
{
  "components": {
    "RESISTOR": {
      "count": 3,
      "values": ["1k0", "4k7", "10k"]
    },
    "CAP": {
      "count": 2,
      "values": ["1uF", "2uF"]
    },
    "74HC08": 1
  },
  "connections": [
    {
      "net": "N_FILTER",
      "endpoints": [
        {"component": "R1", "pin": "2"},
        {"component": "C1", "pin": "1"}
      ]
    }
  ],
  "layout": {
    "strategy": "beautify"
  }
}
```

An explicit donor may be supplied with:

```json
{
  "donor": "proteus_ic/donors/path/to/donor.pdsprj",
  "components": {
    "7490": 4
  }
}
```

## Installation And CLI

Requires Python 3.11 or newer.

```powershell
python -m pip install -e .
```

Core commands:

```powershell
proteusgen validate examples\single_resistor_vcc_gnd.json
proteusgen inspect donor.pdsprj
proteusgen generate-resistors input.json --outdir out\resistor
proteusgen generate-mixed-passives input.json --outdir out\passive
proteusgen generate-mixed-rcl input.json --outdir out\rcl
proteusgen generate-source-driven input.json --outdir out\source
proteusgen generate-ic-combinational input.json --outdir out\logic
proteusgen generate-ic-native input.json --outdir out\native
proteusgen plan-component-placement input.json --output out\plan.json
proteusgen generate-component-placement input.json --output out\components.pdsprj
proteusgen plan-layout input.json --layout-strategy beautify
proteusgen compare expected.pdsprj actual.pdsprj
proteusgen record-result result.json
```

When the package is installed outside this checkout, set
`PROTEUSGEN_REPO_ROOT` to this repository so donors, fixtures, schemas, and
knowledge files can be found.

## Important Limits

- The accepted resistor-heavy component-placer ceiling is `R91`.
- The placer never creates extra `SWITCH` or `POT-HG` packets.
- Seven-segment output requires donor-derived D20 infrastructure. D20 is not
  counted as a requested diode and is not moved by the beautifier.
- Common-cathode display output retains donor-final infrastructure required by
  the accepted object stream.
- The full donor CDB/device skeleton is currently safer than aggressive CDB
  pruning.
- Generated component counts cannot exceed usable packets in the selected
  donor.
- `VSINE` is emitted only when explicitly requested.
- Proteus 8.13 is the final authority. Static validation cannot replace
  open/render/simulation testing.

See [`docs/current_limitations_bridges_costs_and_roadmap.md`](docs/current_limitations_bridges_costs_and_roadmap.md)
for the operational details.

## Validation Model

Every stage is expected to provide:

1. a validator for its direct output;
2. a cumulative validator covering accepted earlier stages;
3. user-specification checks;
4. an information-completeness decision;
5. participation in the final whole-project validator.

Component-placement manifests currently record:

- selected and hidden packets;
- value mutation plans and errors;
- wiring intent and same-net groups;
- actual binary layout translations;
- overlap and bounds checks;
- component packet validation;
- generated-output validation;
- immutable infrastructure checks.

## KiCad Backend

The repository also includes an offline KiCad project writer. It is separate
from the Proteus binary internals but shares the installed CLI:

```powershell
proteusgen generate-kicad input.json --outdir out\kicad
proteusgen plan-kicad-layout input.json
proteusgen generate-kicad-target-pack --outdir out\kicad-targets
proteusgen quality-kicad path\to\project
```

The KiCad backend emits self-contained `.kicad_pro` and `.kicad_sch` projects,
uses source-mined or embedded local symbols, and routes ordinary nets with
orthogonal segments or local labels. Its generated run directories are local
artifacts and are not committed.

See [`kicad/README.md`](kicad/README.md).

## Repository Map

```text
src/proteusgen/  deterministic Proteus generators, parsers, planners, validators
kicad/           separate KiCad backend and source-guided writer
tests/           regression and contract tests
knowledge/       accepted rules, open questions, test results, component data
docs/            architecture, current status, binary research, continuation memory
schemas/         CircuitIR, validation, manifest, and result contracts
prompts/         planner guidance for converting text into JSON
fixtures/        small clean projects with provenance and hashes
proteus_ic/      IC registries and trusted manual donor corpus
experiments/     committed acceptance packs and evidence; local runs are ignored
tools/           reproducible analyzers and dated experiment generators
```

Start documentation reading at [`docs/README.md`](docs/README.md). The
continuation memory is
[`docs/active_working_memory_2026_06_23.md`](docs/active_working_memory_2026_06_23.md).

## Engineering Rules

No byte guess becomes a feature because it looked plausible once.

A rule is promoted only after:

1. byte-level donor comparison;
2. deterministic generation through shared code;
3. stage-specific validation;
4. cumulative regression validation;
5. Proteus open/render/simulation feedback;
6. permanent recording in `docs/` and `knowledge/`.

Experiments must update an existing shared script where possible, include a
Markdown test description, and record user results before the next variant is
built.

## Repository Hygiene

Do not commit:

- Proteus `.workspace` sidecars;
- `Project Backups` and autosaves;
- debug/probe scratch outputs;
- IDE and dependency caches;
- generated KiCad run directories;
- API keys, database URLs, Firebase credentials, or local `.env` files.

Manual donors, source code, schemas, accepted evidence, and compact result
records belong in the repository.
