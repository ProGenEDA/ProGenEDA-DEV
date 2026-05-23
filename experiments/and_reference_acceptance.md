# AND Reference Acceptance Gate

## Intended generated circuit

`examples/and_reference_pending_d05.json` describes the first composed-output milestone:

- one `U1` quad `74HC08` package rendered as units A-D
- `R1=10k` pull-up branch for labelled inputs `1,3,5,7`
- `R2=10k` pull-down branch for labelled inputs `2,4,6,8`
- visible terminal labels, rail wire segments, and junctions

## Evidence currently available

- E001 is a clean Proteus 8.13 base.
- HC08 D01-D03 are clean donor projects; D02 supplies four unwired units, and D03 supplies logic stimulus/probe observations.
- Clean passive fixture projects establish resistor/terminal evidence in isolation.
- Prior `G04_FINAL_picture_circuit_full_cdb` is not acceptance evidence: its project internals are identical to D03 and it contains no target resistor network.

## Gate

Do not enable production rendering of the AND acceptance circuit until a user-created Proteus 8.13 `HC08_D05_exact_picture_manual_control.pdsprj` is committed as an oracle fixture with provenance/hash metadata, inspected, and used for comparison of a generated output that opens and saves correctly in Proteus 8.13.
