# KiCad V4 Embedded Symbols Failure + Manual Donor Request

## Observed result

User tested `KICAD_GENERATED_OUTPUTS_V4_EMBEDDED_SYMBOLS.zip`.

KiCad error shown:

```text
Error loading schematic ...
Unterminated delimited string in ... OPEN_THIS_PROJECT__diode_iv__SCHEMATIC_FILE.kicad_sch,
line 189, offset 25.
```

## Interpretation

V2 proved the basic schematic file could open after wire splitting.

V3 proved project-local library table/downloader was not sufficient on the user's KiCad installation; symbols still showed red question-mark placeholders.

V4 attempted embedded symbol cache blocks but failed schema/string parsing. The error is now likely in the generated embedded `lib_symbols` S-expression text, not in the project shell or original wire segmentation.

## Decision

Stop blind embedded-symbol generation until we have manually-made KiCad donor projects.

Manual donors should be created fresh in KiCad, saved normally, zipped whole project folder, and uploaded for diff/learning.

## Requested manual donor order

```text
KICAD_MANUAL_00_EMPTY_PROJECT.zip
KICAD_MANUAL_01_DIODE_IV.zip
KICAD_MANUAL_02_RC_LOWPASS.zip
KICAD_MANUAL_03_1R_VDC_GND.zip
```

Minimum first upload if user wants to save time:

```text
KICAD_MANUAL_00_EMPTY_PROJECT.zip
KICAD_MANUAL_01_DIODE_IV.zip
```

## What to inspect from donors

```text
.kicad_pro project metadata
.kicad_sch root structure
lib_symbols cache format actually emitted by user's KiCad version
symbol instances for Device:R, Device:C, Device:D, Simulation_SPICE:VDC/VSIN, power:GND
wire segment structure
text directive structure
sym-lib-table behavior if present
resaved formatting and quoting rules
```

## Next fix after donor upload

Build `kicad/generator/kicad_visual_generator_v2.py` or patch current generator to match the user's KiCad output style exactly:

```text
manual donor -> parser/diff notes -> generated exact schema-compatible project -> static lint -> user open test
```
