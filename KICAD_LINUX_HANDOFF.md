# Progen KiCad Linux Handoff

Snapshot date: 2026-07-01

Source repository:

```text
C:\Users\Empty\Documents\Progentotal\protuesgen
```

Git state at packaging:

```text
branch: codex/generic-proteus-generator-v0
commit: 3fe1d1d0
```

## What We Are Building

Progen is a deterministic circuit generator. A strict CircuitIR JSON document is
converted into a schematic project without requiring an AI model inside the core
generator.

The long-term product ships Proteus and KiCad generation through one CLI and one
eventual executable. The KiCad backend remains internally separate from the
Proteus binary-record generator.

KiCad V1 currently targets self-contained `.kicad_pro` and `.kicad_sch` projects.
It supports passive components, sources, ground, labels, many digital and analog
parts, deterministic placement, orthogonal routing, embedded symbols, manifests,
and static/KiCad CLI validation.

## Important Architecture

```text
kicad/generator/kicad_json_to_project.py
    CircuitIR normalization, placement, symbol instances, labels, no-connects,
    schematic/project writing, and manifest output.

kicad/generator/orthogonal_router.py
    Reusable two-dimensional Manhattan router. Wires contain exactly two points
    and are horizontal or vertical.

kicad/generator/symbol_cache.py
    Loads exact source-mined symbols when available and falls back to embedded
    project-local symbols.

kicad/source_pack/
    Bundled KiCad source references used to preserve the file-writing contract.
    The 2026-07-01 audit found all 16 required reference files.

kicad/automation/generate_target_pack.py
    Offline C01-C55 regression-project generator.

kicad/automation/generate_hard_prompt_projects.py
    Converts the three large manually specified stress circuits into offline
    CircuitIR projects.

kicad/automation/quality_check.py
    Static schematic validation and optional `kicad-cli sch erc` validation.

src/proteusgen/cli.py
    Shared Progen CLI integration.
```

## CircuitIR and Output

The KiCad schema identifier is:

```text
progen-kicad-circuit-ir/v1
```

Primary commands:

```bash
python -m proteusgen generate-kicad input.json --outdir out/project
python -m proteusgen plan-kicad-layout input.json
python -m proteusgen generate-kicad-target-pack --outdir out/target_pack
python -m proteusgen quality-kicad out/project
python -m proteusgen kicad-source-reference
```

Each generated project normally contains:

```text
OPEN_THIS_PROJECT__<slug>__PROJECT_FILE.kicad_pro
OPEN_THIS_PROJECT__<slug>__PROJECT_FILE.kicad_sch
progen_generated.kicad_sym
sym-lib-table
input.json
manifest.json
```

## Routing Rules

- Every generated wire is orthogonal and has exactly two endpoints.
- Ordinary two-pin and analog nets use physical Manhattan wires.
- Multi-endpoint nets use deterministic trunks and explicit junctions where
  appropriate.
- Rails and broad digital control/fanout nets may use repeated local labels to
  avoid unsafe sheet-spanning wires.
- Same-name KiCad local labels are intentional electrical connections.
- Local labels are emitted with visible short stubs when safe.
- A local-label stub that cannot be placed without crossing a foreign net is
  skipped instead of emitting an electrically incorrect merged net.
- Generated manifests record components, routes, local-label stubs, junctions,
  no-connect markers, warnings, and source-reference information.

## Symbol Strategy

Exact source-mined symbols are used where available, including:

```text
Device:R
Device:L
Simulation_SPICE:VDC
Simulation_SPICE:VSIN
power:GND
```

Other supported parts can be emitted as self-contained project-local symbols.
This currently covers capacitors, current sources, switches, diodes, LEDs,
transistors, op-amps, display drivers, counters, shift registers, multiplexers,
adders, comparators, and common `40xx`/`74HC` devices.

## Validation State

- The moved repository contains 57 clean Git-tracked files under `kicad/`.
- Generator, router, source pack, target-pack automation, quality checker, CLI
  integration, and KiCad tests are present.
- The bundled source-pack loader reports all 16 required reference files.
- The credential scan found no Groq, MongoDB, Gemini, Hugging Face, or similar
  raw credentials in the packaged source set.
- The user previously opened the C01-C55 generated projects in KiCad and
  confirmed that projects opened, requested components were present, and
  same-name local labels behaved as connected nets.
- Previous Windows testing used KiCad CLI 10.0.3.

Packaging-time regression check on 2026-07-01:

```text
KiCad generator tests: 8 passed
Target projects generated with a short Windows temp root: 55/55
Target-pack assertion: 1 failed
```

The remaining assertion expects at most three router warnings in any target,
while the current generator produces a maximum of four. This is a stale
acceptance threshold, not a failed project generation. Review the four warnings
before either reducing them in the router or changing the test threshold.

Using pytest's deeply nested default Windows temporary path initially generated
52/55 projects because C08, C16, and C55 exceeded the legacy Windows path-length
limit. All three generated under the shorter temp root. Linux should not have
this Windows `MAX_PATH` failure.

The old untracked `kicad/experiments/runs/` output directories are not present
in the moved repository. They are generated evidence, not required source code.
Regenerate them on Linux before accepting a new release.

## Known Work Still Open

1. Re-run the full C01-C55 pack and KiCad CLI quality stage on Linux.
   Confirm the current maximum of four router warnings and then resolve or
   explicitly accept the threshold.
2. Re-run the three very large hard-prompt projects, especially the
   239-component project.
3. Continue improving dense IC actual-wire routing. Local labels remain the safe
   fallback until foreign-net crossing avoidance is proven on large designs.
4. Replace more project-local generic symbols with exact KiCad-library-derived
   symbols and pin definitions.
5. Add stricter ERC modeling for unused pins and power flags. The quality checker
   currently tolerates isolated labels, library-symbol version mismatch,
   un-driven power pins, and intentionally unused pins.

## Linux Setup

Use Python 3.11 or newer:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

Install KiCad through the Linux distribution or KiCad package source so
`kicad-cli` is on `PATH`, then run:

```bash
python -m pytest tests/test_kicad_generator.py tests/test_kicad_target_pack.py -q
python -m proteusgen kicad-source-reference
python -m proteusgen generate-kicad-target-pack --outdir kicad/experiments/runs/linux_c01_c55
python -m proteusgen quality-kicad kicad/experiments/runs/linux_c01_c55
```

`quality_check.py` first uses `shutil.which("kicad-cli")`, so it works on Linux
without the Windows fallback path.

## Archive Scope

This handoff archive contains:

- all Git-tracked files under `kicad/`
- the complete Git-tracked `src/proteusgen/` package used by the shared CLI
- KiCad generator and target-pack tests
- `pyproject.toml`, `AGENTS.md`, and the repository README
- this handoff document

Python bytecode, `__pycache__`, `.env` files, generated run folders, Git
metadata, and credentials are intentionally excluded.
