# ProGenEDA-Memory

## Proteus

ProGenEDA-Memory is an evidence-driven native Proteus circuit generator. It
turns a structured circuit request into a `.pdsprj` project by selecting
complete donor-native component packets, arranging them, adding supported
grid-attached terminals and short pin wires, editing safe values, and
validating the resulting project in Proteus.

The current Proteus implementation is in [`proteus/active`](proteus/active).
Its portable application is
[`proteus/active/release/ProgenProteus.exe`](proteus/active/release/ProgenProteus.exe).

### GPT-5.6 implementation phase

GPT-5.6 built the current operational Proteus system: it repaired and
stabilized the component placer, consolidated terminal placement into one
shared route, implemented grid-attached short-wire terminal behavior, added
the value/properties editor, built the portable executable, and organized the
runtime donors, catalogue, validation, and documentation into the active
backend.

It also directed automated analysis and local Proteus open/save/cold-reopen
checks. That replaced the earlier workflow where every generated circuit had
to be opened and checked manually, making large regression and scale testing
practical.

For the detailed record, see
[`proteus/active/GPT_5_6_PROGRESS.md`](proteus/active/GPT_5_6_PROGRESS.md).

### Current pipeline

```text
Circuit JSON / CircuitIR
  -> input and catalogue validation
  -> donor-backed component placement
  -> arrangement and coordinate beautification
  -> shared catalogue-driven terminal placement
  -> optional value/properties editing
  -> binary validation and local Proteus acceptance gate
  -> native .pdsprj output
```

The component placer is deliberately replaceable. Downstream stages consume a
placed-design contract—component identity, complete native packet, bounds and
pin descriptors—rather than depending on a fixed mega-donor slot or template
coordinate.

### Use the latest executable

`ProgenProteus.exe` is rebuilt from the active source and includes its locked
runtime donor closure. From the repository root:

```powershell
.\proteus\active\release\ProgenProteus.exe generate `
  .\proteus\active\examples\progen_proteus_r_c_value_edit.json `
  --output .\out\r_c_terminalized.pdsprj
```

Other commands:

```powershell
.\proteus\active\release\ProgenProteus.exe --help
.\proteus\active\release\ProgenProteus.exe inspect .\out\r_c_terminalized.pdsprj
.\proteus\active\release\ProgenProteus.exe edit-values <input.pdsprj> --edits <values.json> --output <output.pdsprj>
```

The executable uses the same pipeline as the Python interface. Its build and
smoke-test record is in
[`proteus/active/release/README.md`](proteus/active/release/README.md).

### Use the Python pipeline directly

No executable is required. Set the active source root, then use the same CLI
entry point:

```powershell
$env:PYTHONPATH = "proteus/active/src"
python -m proteusgen.proteus_cli generate `
  proteus/active/examples/progen_proteus_r_c_value_edit.json `
  --output out/r_c_terminalized.pdsprj
```

When installed from the checkout, the equivalent public command is:

```powershell
progen-proteus generate proteus/active/examples/progen_proteus_r_c_value_edit.json --output out/r_c_terminalized.pdsprj
```

Python callers can build a request and invoke the application directly:

```python
import json
from pathlib import Path
from proteusgen.proteus_app import generate_proteus_project

payload = json.loads(
    Path("proteus/active/examples/progen_proteus_r_c_value_edit.json").read_text(
        encoding="utf-8"
    )
)
result = generate_proteus_project(
    payload,
    Path("out/r_c_terminalized.pdsprj"),
)
print(result.output)
```

The input schema, examples, catalogue, and supported property syntax are in
[`proteus/active/schemas`](proteus/active/schemas),
[`proteus/active/examples`](proteus/active/examples), and
[`proteus/active/knowledge/component_catalog_v0.json`](proteus/active/knowledge/component_catalog_v0.json).

### Current component support in the latest executable

The locked mega donor supports bare placement of **56 component families**:

| Group | Families |
| --- | --- |
| Passives and discrete (24) | `RESISTOR`, `CAP`, `CAP-ELEC`, `REALIND`, `DIODE`, `1N4007`, `1N4148`, `1N4733A`, `1N6000B`, `40EPS08`, `BZX55C5V1`, `BZX79C5V1`, `BZY88C`, `LED-RED`, `BRIDGE`, `FUSE`, `NPN`, `PNP`, `2N3904`, `2N4401`, `NMOSFET`, `2N7000`, `BS170`, `TRAN-2P2S` |
| Analog, timing, controls (6) | `LM317T`, `LM741`, `OPAMP`, `NE555`, `POT-HG`, `SWITCH` |
| Sources (4) | `VSOURCE`, `CSOURCE`, `VPULSE`, `VSINE` |
| Displays (2) | `7SEG-COM-AN-BLUE` (`7SEGCOMA`), `7SEG-COM-CAT-BLUE` (`7SEGCOMK`) |
| IC packages (20) | `4027`, `4511`, `7447`, `7490`, `74HC00`, `74HC02`, `74HC04`, `74HC08`, `74HC151`, `74HC157`, `74HC160`, `74HC174`, `74HC192`, `74HC266`, `74HC283`, `74HC32`, `74HC74`, `74HC76`, `74HC85`, `74HC86` |

Default terminalized executable generation is currently promoted for these
**18 two-pin families**:

`RESISTOR`, `CAP`, `CAP-ELEC`, `REALIND`, `DIODE`, `1N4007`, `1N4148`,
`1N4733A`, `1N6000B`, `40EPS08`, `BZX55C5V1`, `BZX79C5V1`, `BZY88C`,
`LED-RED`, `VSOURCE`, `CSOURCE`, `VSINE`, and `VPULSE`.

All other placement-supported families can be deliberately emitted without
terminals using `--no-terminals`. `FUSE` and `SWITCH` are explicitly blocked
from the combined terminal route. Multi-pin terminal and arbitrary-net wiring
are not promoted as general executable features yet; the generator rejects
unsafe requests instead of silently inventing Proteus binary records.

### Repository structure

```text
proteus/
  active/          current package, executable, tests, docs, schemas, catalogue,
                   fixtures, runtime donor closure, and operational evidence
  experiments/     dated trials, generated packs, runner scripts, imports, reports
  archive/         retained historical donors, backups, legacy entry points, docs
```

The generated hash-backed map is
[`proteus/active/REPOSITORY_MAP.md`](proteus/active/REPOSITORY_MAP.md). It
links to the complete inventory, active manifest, ignored-local-items record,
and archive indexes.

### Verify a generated project locally

Run the normal Proteus loader gate on a disposable copy:

```powershell
powershell -ExecutionPolicy Bypass -File proteus/active/tools/invoke_local_proteus_gate.ps1 `
  -Project out/r_c_terminalized.pdsprj
```

This cold-opens the project, waits for the schematic to stabilize, checks for
loader dialogs, cold-reopens it, and records whether Proteus changed the copy.
For implementation details, current limitations, tests, and experiment
evidence, start at [`proteus/active/README.md`](proteus/active/README.md).
