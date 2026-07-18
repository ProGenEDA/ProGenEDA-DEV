# Progen KiCad Workspace

This is the active source-backed KiCad backend. It is separate from the Proteus
binary generator and can run directly from source or through the portable
`progen-kicad` executable.

## Codex 5.6 active delivery

> **CODEX 5.6 TURNED THE KICAD WORKSPACE INTO A COMPLETE BACKEND.**
>
> The Codex 5.6 phase took this folder beyond the early placer experiments and
> built the active deterministic pipeline: tolerant main-JSON repair,
> source-backed symbol/pin resolution, placement, arrangement, beautification,
> wire/terminal/combination handling, native schematic writing, values,
> expected-net validation, bounded PCB generation, packaging, executable
> delivery, and corpus qualification.

Compared with the 5.5-era incremental state, 5.6 delivered a dramatic jump in
both scope and proof. It made the stages independently replaceable while also
making them run as one production flow, retained every candidate variation and
validator report, built the practical 400-circuit corpus, and repaired the
multi-unit source-pin clearance issue through the shared generator rather than
special-casing outputs. The finished portable was then checked through KiCad
10.0.4 netlist export and DRC.

The current evidence is the immutable 390-project qualification base plus a
clean, separately regenerated ten-project KQ26 clearance supplement. Details
are in [`qualification/RESULTS_2026_07_17.md`](qualification/RESULTS_2026_07_17.md).

## Active production entry points

Use the released portable:

```bash
unzip release/progen-kicad-portable-2026_07_17_kq26_clearance_v1.zip
./progen-kicad-portable/progen-kicad run INPUT.json \
  --output-root /tmp/progen-kicad-runs --routing-mode combination
```

Or use the exact committed generator source directly:

```bash
PYTHONPATH=. python -m kicad.pipeline.progen_kicad_executable run INPUT.json \
  --output-root /tmp/progen-kicad-runs --routing-mode combination
```

`run-pcb` exposes only boards that independently pass the physical stage.
`run-variations` creates retained deterministic arrangement variants. See
[`pipeline/README.md`](pipeline/README.md) for all commands and
[`FINALIZATION_STATUS.md`](FINALIZATION_STATUS.md) for the current support
boundary.

Current accepted schematic status, the first PCB target, and the complete
cross-EDA/LTspice handoff are recorded in:

```text
kicad/FINALIZATION_STATUS.md
kicad/PROGENEDA_PROJECT_AND_LTSPICE_HANDOFF.md
```

Historical note: later sections of this README preserve the early incremental
placer-era record and may describe stages as placeholders. Use the two files
above for the current accepted pipeline and next-step status.

## Historical V1 Mode And Shared CLI

KiCad generation writes self-contained projects from
`progen-kicad-circuit-ir/v1` JSON:

```text
python -m proteusgen generate-kicad input.json --outdir out/kicad_project
python -m proteusgen plan-kicad-layout input.json
python -m proteusgen generate-kicad-target-pack --outdir out/kicad_target_pack
python -m proteusgen kicad-source-reference
```

Each project folder contains:

```text
OPEN_THIS_PROJECT__<slug>__PROJECT_FILE.kicad_pro
OPEN_THIS_PROJECT__<slug>__PROJECT_FILE.kicad_sch
input.json
manifest.json
```

Open the `.kicad_pro` file.

## Historical Incremental Pipeline Work

The new architecture is being added one proven slice at a time. The active
slice is placer-only:

```text
CircuitIR JSON -> Placement Input Validator -> Component Placer -> Placement Validator
```

Run it with:

```text
python -m kicad.pipeline.kicad_component_placer kicad/examples/placer_run_<date>_<label>/inputs --run-dir kicad/examples/placer_run_<date>_<label> --run-label <label>
```

For partial CircuitIR-shaped placer inputs, it writes an openable KiCad project:

```text
OPEN_THIS_PROJECT__<slug>__PLACER.kicad_pro
OPEN_THIS_PROJECT__<slug>__PLACER.kicad_sch
```

It also writes `placement.json` and `placement_trace.json` as debug evidence.
Later stages are listed as placeholders under `kicad/pipeline/placeholders.py`
but are intentionally not active yet.

The placer-only path does not require KiCad to be installed. It uses embedded
repo metadata for component sizes and source-backed generator kind specs.

The 20 practical placer examples are partial `progen-kicad-placer-ir/v0.2`
objects shaped like the full `progen-kicad-circuit-ir/v1` contract: they use
`project`, `components`, `nets`, component `id`, `kind`, and `value`. Pins and
net membership are intentionally omitted until wire/terminal stages own those
decisions.

The examples are under:

```text
kicad/examples/placer_run_2026_07_01_baseline_c11_spacing_fix_v2/
kicad/examples/placer_run_2026_07_01_stress_limit_suite_v2/
```

Generated example folders are immutable records. Create a new `placer_run_*`
folder for every changed generation.

## Source-Guided Writing

The generator bundles a KiCad source-pack zip under
`kicad/source_pack/downloaded_zip/`. At generation time it records the source
hashes and uses mined exact symbol blocks where available for core V1 parts:

```text
Device:R
Device:L
Simulation_SPICE:VDC
Simulation_SPICE:VSIN
power:GND
```

Broader parts are emitted as embedded project-local symbols when an exact mined
symbol is not available. This includes capacitors, current sources, switches,
diodes, LEDs, transistors, op-amps, display drivers, counters, shift registers,
muxes, adders, comparators, and common `40xx`/`74HC` ICs.

## Routing Rules

The router is a reusable orthogonal module:

- every physical wire object has exactly two points
- every physical wire is horizontal or vertical
- ordinary two-pin and analog/local nets route through Manhattan wires
- rails and broad digital bus/control nets use repeated KiCad local labels to
  avoid sheet-spanning wires and crossing-heavy IC schematics
- generated manifests record wire segments, local-label placements, warnings,
  source references, and static validation results

## Target-Pack Evidence

The offline C01-C55 pack is generated by:

```text
python kicad/automation/generate_target_pack.py --outdir kicad/experiment_records/runs/local_20260613_target_pack_c01_c55_v3
```

The latest checked run produced 55 projects with 55 static-valid outputs.

## User KiCad Open Result - 2026-06-14

User opened the generated C01-C55 KiCad projects and reported:

- projects open in KiCad
- components are present and match the requested circuit families
- same-name labels appear on component pins and behave as connected nets when
  symbols/wires are dragged
- some nets are intentionally connected by local labels instead of long visible
  wires

This local-label behavior is intentional generator output. It comes from the
orthogonal router policy for rails and broad digital bus/control nets. KiCad
local labels electrically connect same-name nets without requiring one long
sheet-spanning wire. Ordinary local/analog nets can still be emitted as physical
Manhattan wire segments.

The behavior is generated by code, not manual editing. The relevant generator
path is:

```text
kicad/generator/orthogonal_router.py
kicad/generator/kicad_json_to_project.py
```

The source-guided part is the file/schematic writing contract and exact mined
core symbols. Broad IC/helper symbols are currently embedded as project-local
symbols when exact KiCad library symbols have not yet been mined.

## Local KiCad CLI

This Linux workspace has KiCad 10.0.4 unpacked from the AppImage under
`kicad/.local/`. The CLI can be run directly:

```text
kicad/.local/bin/kicad-cli --version
```

Observed version:

```text
10.0.4
```

Open the GUI through the helper script:

```text
kicad/tools/open_local_kicad.sh
```

Quality command for the current placer baseline:

```text
python -m kicad.automation.quality_check kicad/examples/placer_run_2026_07_01_baseline_c11_spacing_fix_v2 --kicad-cli kicad/.local/bin/kicad-cli
```

Result on 2026-07-01:

- 20 schematics checked.
- 20 passed.
- 0 failed.
- ERC reports still include tolerated placer-stage no-wire issues until the
  wire, terminal, and value stages exist.
