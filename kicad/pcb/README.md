# Integrated KiCad PCB Pipeline

Status date: 2026-07-18

This package is the bounded native KiCad PCB stage of the canonical ProGenEDA
pipeline. It consumes the same fixed main JSON and exact resolved schematic pin
geometry used by schematic generation. It does not accept a separate PCB input.

## Current PCB Delivery

The current implementation built this from a small proof target into the active bounded physical
stage: source-footprint provenance, symbol-pin-to-pad mapping, square-fill
placement, two-layer routing variants, no-installation parsing and validation,
artifact packaging, and external KiCad DRC evidence. The current delivery improvement over the
earlier prototype work is visible in the contract: the PCB uses the same canonical
JSON as the schematic, ships only after every physical check passes, and keeps
all accepted/rejected variations for audit instead of pretending that an
unrouted board is usable.

The current common-400 release qualification produced 311 accepted boards and
89 explicit withholds. The current implementation then used the discovered KQ26 multi-unit
pin/body-clearance case to strengthen the shared schematic settlement logic;
the ten repaired profiles all produced accepted boards, and the packaged KQ26
smoke board passed KiCad 10.0.4 DRC with zero violations and zero unconnected
items. The complete schematic/PCB release record is in
[`../qualification/RESULTS_2026_07_17.md`](../qualification/RESULTS_2026_07_17.md).

## Runtime Architecture

```text
canonical main JSON
-> validated KiCad schematic placement/pin contract
-> physical_design_compiler
-> footprint_placer
-> pcb_router (two copper layers, route variants/retries)
-> kicad_pcb_writer
-> independent kicad_pcb_parser
-> pcb_validator
-> output_packager
```

Modules:

- `physical_design_compiler.py`: selects only components whose logical pins can
  be resolved to pads in a bundled real footprint. Omissions always include a
  reason.
- `footprint_placer.py`: deterministic square-fill shelf placement with source
  courtyard bounds and SMD fanout halos.
- `pcb_router.py`: deterministic F.Cu/B.Cu A* routing with SMD escape lanes,
  edge-level occupancy, via restrictions, high-fanout retries, and retained
  variants.
- `kicad_pcb_writer.py`: writes a native `.kicad_pcb` using exact bundled KiCad
  footprint source. Full reference identities are retained in footprint
  properties and hidden on silkscreen to prevent long-name collisions.
- `kicad_pcb_parser.py`: parses the emitted board without KiCad.
- `pcb_validator.py`: independently validates identity, values, exact pad-net
  membership, copper connectivity, track/pad/via clearance, no-net copper,
  drilled-hole clearance, placement, and board outline.
- `pipeline.py`: owns acceptance. A board reaches user output only when every
  hosted check passes.

## No-KiCad Runtime Contract

Generation and primary validation do not require KiCad, `kicad-cli`, system
footprint libraries, or network access. The committed source pack is:

```text
kicad/pcb/source_pack/footprint_source_pack.json
```

It contains exact KiCad 10.0.4 `.kicad_mod` source text, parsed pads/bounds,
SHA-256 digests, and source provenance. Four upstream KiCad 10.0.4 PCB
S-expression source/parser files are retained under
`source_pack/kicad_source/` as implementation references. Runtime catalogue
loading verifies each footprint digest before use.

Installed KiCad is an external release oracle only. Reproducible corpus DRC is
run by:

```bash
PYTHONPATH=. python kicad/tools/validate_pcb_corpus_with_kicad.py RUN_DIR \
  --output-dir NEW_ORACLE_DIR --jobs 12
```

The oracle tool supports `--resume`; it never requires regenerating the 600
projects after an interrupted DRC pass.

## Bundled Footprint Support

The source pack has 34 exact records:

- axial resistor, ceramic capacitor, radial electrolytic capacitor;
- DO-41 diode and 5 mm THT LED;
- DIP-8, DIP-14, DIP-16, SOIC-8;
- TO-220-3 and TO-92 inline;
- two-pin Altech terminal block;
- Arduino Nano module;
- ESP32-WROOM-32 module;
- 1x01 through 1x20 2.54 mm vertical pin headers.

The abstract mapping is centralized in
`kicad/pipeline/catelogues/kicad_footprint_map.json`. Adding support means adding
one audited footprint source record and one mapping, then extending focused
tests. Downstream stages do not contain component-name special cases.

## Output Contract

For an accepted board:

- the user project zip contains `.kicad_pro`, `.kicad_sch`, and `.kicad_pcb`;
- `outputs/<id>/user_pcb/<name>.kicad_pcb` provides direct PCB access;
- the internal bundle retains physical design, process profile, placement,
  route plan, every attempted route variant, candidate board, parser/validator
  reports, main input, and all schematic-stage JSON.

For `no_supported_physical_components`, `pcb_routing_limit`, or
`pcb_validation_failed`, no user PCB is created. The schematic project still
completes, and all PCB diagnostics remain internal. There is no fixed
component-count or multi-pad-net-count rejection: every physically compilable
design receives placement and bounded routing attempts.

## Current Bounds

This is a hardened MVP PCB slice, not a universal production autorouter.

- two copper layers;
- adaptive routing profiles: fine 1.27 mm grid for small/medium boards and a
  bounded 2.54 mm lattice plus three routing-order variants for extra-large
  boards;
- small/medium boards retain global-net-aware placement; dense boards cluster
  local nets and expand toward a square board before routing global rails;
- 0.25 mm generated tracks, 0.8/0.4 mm vias, 0.20 mm minimum clearance;
- explicit source-derived minimum drill rules (0.20 mm where the ESP32 source
  footprint requires it);
- conservative placement and routing space;
- no copper pours, differential-pair constraints, controlled impedance,
  length matching, thermal design, or universal dense-board routing yet.

## Final Evidence

Canonical run:

```text
kicad/examples/progen_kicad_executable_run_2026_07_11_174321_pcb_600_combination_v4
```

- 600/600 input JSONs fixed and generated through the real combination pipeline;
- 600/600 schematic static/final/netlist/geometry/body-overlap checks passed;
- 495 accepted native PCBs;
- 67 historical complexity limits (kept as immutable v4 evidence; current
  code routes these inputs rather than rejecting them by count);
- 38 explicit routing limits;
- zero generic post-routing hosted-validation failures;
- 495 direct PCB artifacts and 600 user/internal archives.

Installed KiCad 10.0.4 oracle:

```text
kicad/examples/pcb_cli_oracle_run_2026_07_11_185217_pcb_600_combination_v4
```

- 495/495 accepted boards checked;
- 495 passed;
- 0 DRC violations;
- 0 unconnected items.

Fabrication and render evidence for MJ001, MJ002, N01, N02, and N20:

```text
kicad/examples/pcb_release_evidence_run_2026_07_11_230157_pcb_600_combination_v4
```

Every selected board exported Gerbers, drill data/report, BOM, position CSV,
and a nonblank KiCad 3D render.

### Additive 67-Case Recovery Evidence

The historical v4 run is immutable. Later changes did not regenerate the 600
inputs from scratch; they reran only its former count-based non-output cases.

```text
kicad/examples/progen_kicad_executable_run_2026_07_12_052149_pcb67_v3_group_[a-d]
```

- the fixed-cap rejection is gone: every selected physically compilable design
  now receives adaptive placement and bounded routing;
- 35 of the former 67 count-based non-outputs became accepted boards;
- KiCad 10.0.4 DRC accepted all 35: 4/4 group A, 4/4 group B, 11/11 group C,
  and 16/16 group D, each with zero violations and zero unconnected items.

The final near-complete rescue evidence covers the 18 remaining inputs that
were within two unfinished physical nets:

```text
kicad/examples/progen_kicad_executable_run_2026_07_13_002708_pcb_near_complete_rescue_2026_07_13_group_[a-c]
kicad/experiment_records/runs/pcb_near_complete_rescue_group_[a-b]_kicad10_drc_2026_07_13
```

- deterministic seed `404` recovered all five recoverable 67-footprint cases;
- 5/5 new boards passed installed KiCad 10.0.4 DRC with zero violations and
  zero unconnected items;
- the remaining 13 near-complete inputs stayed routing-limited by one net even
  after the retained broader seed study. They are never exposed as PCB output.

The effective 600-circuit evidence set therefore has **535 accepted native
PCBs**, all externally DRC clean, and **65 explicit routing limits**. The
production default uses the one proven seed `404`; explicit layout variations
choose alternate retained deterministic orders one at a time, avoiding the
unbounded latency of an eight-seed production retry.
