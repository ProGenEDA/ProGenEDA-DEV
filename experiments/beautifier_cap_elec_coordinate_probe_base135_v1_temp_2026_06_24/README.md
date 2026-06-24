# Beautifier CAP-ELEC Coordinate Probe

Generated on 2026-06-24.

This pack uses the reusable passive-family beautifier probe harness.
It keeps the accepted parsed-coordinate method and avoids creating one-off scripts per component.

## Family

- Family under test: `CAP-ELEC`
- Donor: `proteus_ic\donors\main_mega_20260618\Mega_7segan7segcom74hc0074hc02hc04hc08hc32hc74hc76hc85hc86hc151hc157hc160hc174hc174hc192hc266hc283_4027_4511_7447_7490capcapelecdiodelm741ne555npnpnprealindresistor.pdsprj`
- Donor inventory count: `630`
- Probe variant: `base135`

## Parsed Coordinates Under Test

- `5/9` -> (167365680, 138450320), `length_prefixed_text:C21`
- `74/78` -> (167365680, 137901680), `length_prefixed_text:1uF`
- `151/155` -> (167365680, 137647680), `length_prefixed_text:CAP-ELEC`
- `345/349` -> (167640000, 138176000), `marker_body:CAP-ELEC`

## Test Files

- `00_CE00_CAP-ELEC_1X_BASELINE_NO_BEAUTIFY/CE00_CAP-ELEC_1X_BASELINE_NO_BEAUTIFY.pdsprj`: Baseline control. One `CAP-ELEC` should open in the original donor-selected position.
- `01_CE01_CAP-ELEC_1X_PARSED_COORDS/CE01_CAP-ELEC_1X_PARSED_COORDS.pdsprj`: 1 `CAP-ELEC` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.
- `02_CE02_CAP-ELEC_3X_PARSED_COORDS/CE02_CAP-ELEC_3X_PARSED_COORDS.pdsprj`: 3 `CAP-ELEC` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.
- `03_CE03_CAP-ELEC_5X_PARSED_COORDS/CE03_CAP-ELEC_5X_PARSED_COORDS.pdsprj`: 5 `CAP-ELEC` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.

## User Results

Pending.

## What Success Means

If every `CAP-ELEC` case opens without DLL errors and labels/values stay attached,
coordinate beautification for `CAP-ELEC` is accepted for these counts.
