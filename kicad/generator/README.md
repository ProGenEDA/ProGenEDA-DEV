# KiCad Generator Workspace

This folder retains the persistent source-writing research and component
catalogue work that feeds the active KiCad backend.

## Codex 5.6 Active Generator Delivery

Codex 5.6 took the early source-writing milestones recorded below and connected
them to the complete `kicad/pipeline/` generator: canonical JSON repair,
source-backed symbol/pin use, arrangement, routing, terminals, values,
validators, packaging, and optional PCB output. This is a substantial advance
over the prior 5.5-era isolated writer experiments: the source writer is now
one proven stage in an executable pipeline with expected-net and geometry
acceptance rather than a stand-alone file emitter.

Run the active source generator from the repository root:

```bash
PYTHONPATH=. python -m kicad.pipeline.progen_kicad_executable run INPUT.json \
  --output-root /tmp/progen-kicad-runs --routing-mode combination
```

The final release/qualification details are in
[`../FINALIZATION_STATUS.md`](../FINALIZATION_STATUS.md). The V6/V7 notes below
are preserved because they document the donor/source discovery that Codex 5.6
expanded into the current backend.

## Historical Locked Milestone

V6 is the first source-driven KiCad generator milestone that the user opened successfully in KiCad:

```text
syntax opens
embedded symbols render
pin-endpoint autorouting connects wires correctly
```

The correct writer order is still:

```text
header -> uuid -> paper -> lib_symbols -> schematic items -> sheet_instances
```

## Historical V7 Component Catalog

V7 adds a broad component catalog in:

```text
kicad/generator/kicad_backend/component_catalog.py
```

The catalog currently contains 60 component kinds. It separates components into two tiers:

```text
verified_embedded
cataloged_needs_symbol_cache
```

### Verified embedded / portable now

These have verified embedded symbol-cache blocks from KiCad source fixtures and have already been used in working V5/V6 generated projects:

```text
GND
R
L
VDC
VSIN
```

### Cataloged but not yet fully portable

These have metadata now: KiCad lib id, aliases, pin list, approximate pin-local connection model, SPICE class where relevant, and default value.

```text
C, CP, C_POL, R_POT, FERRITE, FUSE, PTC, MOV, TVS,
D, DIODE, LED, ZENER, SCHOTTKY, BRIDGE,
VPULSE, VAC, IDC, ISIN, IPULSE,
NPN, PNP, NMOS, PMOS, JFET_N, JFET_P,
OPAMP, LM741, LM358, LM393, NE555, L7805, LM317,
74HC00, 74HC04, 74HC08, 74HC32, 74HC86, 74HC74,
74HC76, 74HC90, 74HC157, 74HC192, 4511, 4017,
CONN_2, CONN_3, CONN_4, CONN_6, CONN_8, TESTPOINT,
+5V, +3V3, VCC, GNDA
```

These must not be called fully verified until their symbol-cache blocks and pin endpoints are extracted from real KiCad donor files and tested.

## Run examples

```bash
python kicad/generator/kicad_visual_generator.py --example vdc_resistor_op --out out/vdc_resistor_op
python kicad/generator/kicad_visual_generator.py --example vsin_rl_tran --out out/vsin_rl_tran
```

Open the generated `OPEN_THIS_FIRST__...PROJECT_FILE.kicad_pro` file in KiCad.

## Output package

Each run writes:

```text
*.kicad_pro
*.kicad_sch
*.cir                 # debug-only cross-check netlist
manifest.json
static_checks.json
README_OPEN_FIRST.txt
```

The `.cir` file is not the product. The product is the editable visual KiCad project.

## Master plan

The all-component roadmap is tracked here:

```text
kicad/planning/COMPONENT_MASTER_PLAN.md
```
