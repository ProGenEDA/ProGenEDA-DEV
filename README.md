# ProGenEDA

ProGenEDA is a development repository for deterministic, donor-aware EDA
generation. A backend receives one canonical circuit JSON document, resolves
only supported native records, produces an editable project, and retains
machine-readable validation evidence beside the result.

This repository contains independent backends for Proteus, KiCad, EasyEDA Pro,
and LTspice. They share the canonical circuit intent but do not depend on one
another at runtime.

## Backends

| Backend | Native output | Current entry point | Scope summary |
| --- | --- | --- | --- |
| Proteus | `.pdsprj` | [`proteus/active/`](proteus/active/) | Donor-backed placement, bounded terminal attachment, value editing, and local loader evidence. |
| KiCad | `.kicad_pro`, `.kicad_sch`, optional `.kicad_pcb` | [`kicad/`](kicad/) | Canonical JSON repair, source-backed schematic generation, combination routing, validation, and bounded two-layer PCB output. |
| EasyEDA Pro | `.eprj` | [`Easyeda/`](Easyeda/) | Native SQLite project generation using audited source records, compact schematic routing, and bounded PCB generation. |
| Altium | `.PrjPcb` + source-backed `.SchDoc`, packaged as ZIP | [`Altium/`](Altium/) | Direct native schematic generation from canonical JSON, with source-derived symbols/pins/wires/labels and saved-file validation. Direct PCB output is not qualified yet. |
| LTspice | `.asc` | [`ltspice/`](ltspice/) | Donor-native stock-symbol placement, physical-wire routing, and validated ASC emission. |

Each backend documents its supported catalogue, input restrictions, validation
contract, and release evidence in its own README. A backend must reject or
withhold unsupported work rather than substitute an approximate native record.

## Shared Generation Model

```text
Canonical circuit JSON
  -> normalize and validate input
  -> resolve supported components and pins
  -> place and arrange components
  -> route wires, terminals, or both according to backend policy
  -> edit approved values and references
  -> validate structure, pins, nets, geometry, and backend-specific rules
  -> emit native project plus internal audit artifacts
```

The canonical input remains the source of truth. Generation stages retain their
own reports and accepted or rejected layout/routing variants so a released
project can be traced back to the exact request and decisions that produced it.

## Getting Started

Run backend commands from the repository root. The portable executables are
the normal distribution form; direct source commands use the same pipeline.

### KiCad

```bash
unzip kicad/release/progen-kicad-portable-2026_07_17_kq26_clearance_v1.zip
./progen-kicad-portable/progen-kicad run INPUT.json \
  --output-root /tmp/progen-kicad-runs \
  --routing-mode combination
```

For PCB-only output from the same canonical input:

```bash
./progen-kicad-portable/progen-kicad run-pcb INPUT.json \
  --output-root /tmp/progen-kicad-pcb-runs \
  --routing-mode combination
```

Direct source entry point:

```bash
PYTHONPATH=. python -m kicad.pipeline.progen_kicad_executable run INPUT.json \
  --output-root /tmp/progen-kicad-runs \
  --routing-mode combination
```

See [`kicad/README.md`](kicad/README.md) for the supported input and
[`kicad/pcb/README.md`](kicad/pcb/README.md) for the physical-board boundary.

### EasyEDA Pro

```bash
Easyeda/dist/progen-easyeda run INPUT.json \
  --output-root /tmp/progen-easyeda-runs \
  --routing-mode combination \
  --events ndjson
```

Direct source entry point:

```bash
PYTHONPATH=. python -m Easyeda.executable run INPUT.json \
  --output-root /tmp/progen-easyeda-runs \
  --routing-mode combination \
  --events ndjson
```

See [`Easyeda/README.md`](Easyeda/README.md) and
[`Easyeda/SUPPORTED_COMPONENTS.md`](Easyeda/SUPPORTED_COMPONENTS.md).

### LTspice

```bash
PYTHONPATH=. python -m ltspice INPUT.json \
  --outdir /tmp/progen-ltspice-output \
  --label generated-circuit \
  --engine donor_native
```

The result is a native `.asc` file. The generator and deterministic validators
do not require LTspice to be installed; opening or simulating the output does.
See [`ltspice/README.md`](ltspice/README.md) for the donor-observed support
boundary and packaging instructions.

### Proteus

```powershell
.\proteus\active\release\ProgenProteus.exe generate `
  .\proteus\active\examples\progen_proteus_r_c_value_edit.json `
  --output .\out\r_c_terminalized.pdsprj
```

Direct source entry point:

```powershell
$env:PYTHONPATH = "proteus/active/src"
python -m proteusgen.proteus_cli generate `
  proteus/active/examples/progen_proteus_r_c_value_edit.json `
  --output out/r_c_terminalized.pdsprj
```

See [`proteus/active/README.md`](proteus/active/README.md) for the donor
policy, current terminal boundary, and native loader gate.

## Validation Principles

Every backend owns a deterministic validation path. Depending on the backend,
that includes component/reference checks, pin existence, expected-net
comparison, geometry and clearance checks, source-record provenance, native
file parsing, and optional application/CLI acceptance evidence.

Native application checks are additional evidence, not a substitute for the
backend's own structural validation. Conversely, static validation does not
promote a project that has not satisfied the backend's documented release
contract.

## Qualification Evidence

- KiCad: [`kicad/qualification/README.md`](kicad/qualification/README.md)
  documents the 400-circuit corpus and the bounded PCB results.
- EasyEDA Pro: [`Easyeda/qualification/README.md`](Easyeda/qualification/README.md)
  documents the 300-circuit full-pin corpus.
- LTspice: [`ltspice/docs/COMMON_CIRCUIT_CORPUS.md`](ltspice/docs/COMMON_CIRCUIT_CORPUS.md)
  describes the named native-circuit corpus.
- Proteus: [`proteus/active/examples/proteus_200_circuits/README.md`](proteus/active/examples/proteus_200_circuits/README.md)
  documents the executable-oriented corpus and evidence boundary.

## Repository Map

```text
proteus/    native Proteus backend, active package, donor evidence, experiments
kicad/      KiCad schematic and PCB generator, source pack, qualification, release
Easyeda/    independent EasyEDA Pro backend, audited donor bundle, qualification
Altium/     direct native Altium schematic generator, source pack, validators, research bridge
ltspice/    donor-native LTspice backend, catalogues, pipeline, packaging, tests
pspice/     PSpice/OrCAD research and early generator material
showcase/   curated generated projects for review
tests/      repository-level regression checks
```

Historical experiment folders are preserved as evidence. New generation runs
should create a new run directory and never overwrite prior outputs.

## Documentation Index

- [`kicad/FINALIZATION_STATUS.md`](kicad/FINALIZATION_STATUS.md) - KiCad
  status and release boundary.
- [`kicad/pipeline/MAIN_INPUT_JSON_CONTRACT.md`](kicad/pipeline/MAIN_INPUT_JSON_CONTRACT.md)
  - canonical KiCad input contract.
- [`Easyeda/INPUT_JSON.md`](Easyeda/INPUT_JSON.md) - EasyEDA input contract.
- [`Easyeda/ARCHITECTURE.md`](Easyeda/ARCHITECTURE.md) - EasyEDA stage design.
- [`Altium/README.md`](Altium/README.md) - Altium target status and commands.
- [`Altium/ARCHITECTURE.md`](Altium/ARCHITECTURE.md) - Altium stage contracts.
- [`Altium/INPUT_JSON.md`](Altium/INPUT_JSON.md) - Altium direct input contract.
- [`ltspice/ARCHITECTURE.md`](ltspice/ARCHITECTURE.md) - LTspice donor-native
  architecture and support evidence.
- [`proteus/active/docs/README.md`](proteus/active/docs/README.md) - Proteus
  operational documentation index.
