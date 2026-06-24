# Beautifier Resistor Max Probe V3

Generated on 2026-06-24.

`BEAUTIFIER_RESISTOR_COORDINATE_PROBE_V2_TEMP_2026_06_24` was accepted by user Proteus testing.
This pack uses the same parsed-coordinate movement path for the accepted R91 resistor ceiling.

`690` is only the raw resistor packet inventory found in the current main mega no-source donor.
It is not treated as the safe generation limit because earlier large-rule testing recorded `R91` as accepted.

## Max Count

- Donor: `proteus_ic\donors\main_mega_20260618\Mega_7segan7segcom74hc0074hc02hc04hc08hc32hc74hc76hc85hc86hc151hc157hc160hc174hc174hc192hc266hc283_4027_4511_7447_7490capcapelecdiodelm741ne555npnpnprealindresistor.pdsprj`
- Accepted `RESISTOR` test count: `91`
- Donor inventory count, not accepted limit: `690`

## Parsed Resistor Coordinates Under Test

- `4/8` -> (166095680, 153283920), `length_prefixed_text:R1`
- `73/77` -> (166095680, 153040080), `length_prefixed_text:10k`
- `150/154` -> (166095680, 152786080), `length_prefixed_text:RESISTOR`
- `236/240` -> (166095680, 152786080), `length_prefixed_text:{PRIMITIVE=ANALOGUE}`
- `313/317` -> (165862000, 153162000), `marker_body:RESISTOR`

## Test File

- `00_R04_RESISTOR_91X_ACCEPTED_MAX_PARSED_COORDS/R04_RESISTOR_91X_ACCEPTED_MAX_PARSED_COORDS.pdsprj`: Accepted-limit resistor stress case: 91 resistors should open on the beautifier grid. Check that Proteus does not throw LXLCORE.dll and that labels/values remain near their resistor bodies.

## User Results

Pending.

## What Success Means

If this opens without `LXLCORE.dll` and the resistor labels/values stay with their bodies,
`RESISTOR` coordinate beautification is accepted at the R91 ceiling and we can move to `CAP` next.
