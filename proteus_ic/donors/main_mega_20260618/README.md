# Main Mega Donors 2026-06-18

This folder contains copied, promoted mega donors from:

```text
proteus_ic/donors/manual_downloads_20260616/mega_component_placer
```

The originals remain in the manual-download corpus for auditability. These
copies are the stable main donor paths for the removal-only, no-terminal
component placer.

## Donor Roles

- `semimega_...realindresistor.pdsprj`: small no-source donor.
- `semimega_...realindresistorandsources.pdsprj`: small donor with source
  bodies.
- `15xsemimega_...realindresistorandsources.pdsprj`: large source-capable
  donor.
- `Mega_...realindresistor.pdsprj`: largest no-source donor.

## Supported Families

The trusted manifest records conservative inspected counts for normal package
records:

```text
RESISTOR, CAP, CAP-ELEC, REALIND, DIODE, NPN, PNP
LM741, NE555
VSOURCE, CSOURCE, VSINE
4027, 4511, 7447, 7490
74HC00, 74HC02, 74HC04, 74HC08, 74HC32, 74HC74, 74HC76,
74HC85, 74HC86, 74HC151, 74HC157, 74HC160, 74HC174,
74HC192, 74HC266, 74HC283
```

7-segment displays are supported as special-case display records from the mega
donor, not as normal `U/R/C/L/D/Q/V/I` package records:

```text
7SEG-COM-AN-BLUE / 7SEGCOMA
7SEG-COM-CAT-BLUE / 7SEGCOMK
```

Current accepted display/4027 coexistence requires the visible `D20` pre-display
bridge packet. D20 removal is being tested separately and must not be assumed
safe until a Proteus-confirmed diagnostic passes.
