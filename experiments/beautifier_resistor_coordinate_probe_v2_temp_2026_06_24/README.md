# Beautifier Resistor Coordinate Probe V2

Generated on 2026-06-24.

This pack replaces the rejected V1 fixed passive offset table with parsed coordinate fields.
It intentionally tests only `RESISTOR` movement first.

## Why This Exists

User reported all `BEAUTIFIER_FAMILY_PASSIVES_V1_TEMP_2026_06_23` cases failed with `LXLCORE.dll`.
Byte inspection showed V1 moved packet constants, not true coordinates.

## Parsed Resistor Coordinates Under Test

- `4/8` -> (166095680, 153283920), `length_prefixed_text:R1`
- `73/77` -> (166095680, 153040080), `length_prefixed_text:10k`
- `150/154` -> (166095680, 152786080), `length_prefixed_text:RESISTOR`
- `236/240` -> (166095680, 152786080), `length_prefixed_text:{PRIMITIVE=ANALOGUE}`
- `313/317` -> (165862000, 153162000), `marker_body:RESISTOR`

## Test Files

- `00_R00_RESISTOR_1X_BASELINE_NO_BEAUTIFY/R00_RESISTOR_1X_BASELINE_NO_BEAUTIFY.pdsprj`: Baseline control. One resistor should open in the original donor-selected position. This proves the placer/donor path is still sound before coordinate mutation.
- `01_R01_RESISTOR_1X_PARSED_COORDS/R01_RESISTOR_1X_PARSED_COORDS.pdsprj`: One resistor should move to the beautifier grid. Ref text, value text, model text, property text, and symbol body should stay together. No LXLCORE.dll.
- `02_R02_RESISTOR_3X_PARSED_COORDS/R02_RESISTOR_3X_PARSED_COORDS.pdsprj`: Three resistors should be separated on one row. This checks repeated parsed-coordinate movement without touching the old fixed offsets.
- `03_R03_RESISTOR_5X_PARSED_COORDS/R03_RESISTOR_5X_PARSED_COORDS.pdsprj`: Five resistors should be separated on the grid, with all visible labels still attached to their matching resistor bodies.

## User Results

Pending.

## Next Step

If R00 opens and R01-R03 also open without `LXLCORE.dll`, widen to CAP/REALIND/CAP-ELEC/DIODE one family at a time.
If any parsed-coordinate resistor case fails, stop and inspect the emitted packet diff before trying another family.
