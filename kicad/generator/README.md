# KiCad Generator Workspace

This folder contains the persistent Python generator code for the KiCad backend.

## V5 direction

V5 replaces the earlier guess-based writer with a source-driven writer. The writer mirrors the KiCad schematic save path at a narrow subset level:

```text
header -> uuid -> paper -> lib_symbols -> schematic items -> sheet_instances
```

The first verified embedded-symbol set is intentionally small:

```text
Simulation_SPICE:VDC
Simulation_SPICE:VSIN
Device:R
Device:L
power:GND
```

These symbol-cache blocks were extracted from KiCad upstream QA data, not handwritten. More symbols must be added only after we have a verified saved block from KiCad source fixtures, symbol libraries, or manual donor projects.

## Current V5 artifact

The current generated test ZIP is:

```text
KICAD_GENERATED_OUTPUTS_V5_SOURCE_DRIVEN.zip
```

It includes:

```text
vdc_resistor_op/
vsin_rl_tran/
SOURCE_CODE_SNAPSHOT/
```

The `SOURCE_CODE_SNAPSHOT/` folder contains the modular V5 Python backend. Promote it into this repo folder after the V5 files are confirmed to parse and render in KiCad.

## Run examples after promotion

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
