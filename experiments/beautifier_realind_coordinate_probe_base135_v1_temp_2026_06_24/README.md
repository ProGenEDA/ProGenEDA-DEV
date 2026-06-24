# Beautifier REALIND Coordinate Probe

Generated on 2026-06-24.

This pack uses the reusable passive-family beautifier probe harness.
It keeps the accepted parsed-coordinate method and avoids creating one-off scripts per component.

## Family

- Family under test: `REALIND`
- Donor: `proteus_ic\donors\main_mega_20260618\Mega_7segan7segcom74hc0074hc02hc04hc08hc32hc74hc76hc85hc86hc151hc157hc160hc174hc174hc192hc266hc283_4027_4511_7447_7490capcapelecdiodelm741ne555npnpnprealindresistor.pdsprj`
- Donor inventory count: `600`
- Probe variant: `base135`

## Parsed Coordinates Under Test

- `4/8` -> (163047680, 142514320), `length_prefixed_text:L1`
- `73/77` -> (163047680, 142219680), `length_prefixed_text:1mH`
- `149/153` -> (163047680, 141965680), `length_prefixed_text:REALIND`
- `263/267` -> (163047680, 141965680), `length_prefixed_text:{MODFILE=REALIND}\n{RP=1M}\n{ESR`
- `339/343` -> (163576000, 142240000), `marker_body:REALIND`

## Test Files

- `00_L00_REALIND_1X_BASELINE_NO_BEAUTIFY/L00_REALIND_1X_BASELINE_NO_BEAUTIFY.pdsprj`: Baseline control. One `REALIND` should open in the original donor-selected position.
- `01_L01_REALIND_1X_PARSED_COORDS/L01_REALIND_1X_PARSED_COORDS.pdsprj`: 1 `REALIND` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.
- `02_L02_REALIND_3X_PARSED_COORDS/L02_REALIND_3X_PARSED_COORDS.pdsprj`: 3 `REALIND` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.
- `03_L03_REALIND_5X_PARSED_COORDS/L03_REALIND_5X_PARSED_COORDS.pdsprj`: 5 `REALIND` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.

## User Results

Pending.

## What Success Means

If every `REALIND` case opens without DLL errors and labels/values stay attached,
coordinate beautification for `REALIND` is accepted for these counts.
