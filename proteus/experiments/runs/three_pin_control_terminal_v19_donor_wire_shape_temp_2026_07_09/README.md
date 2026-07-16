# Three-pin control terminal V19 donor wire-shape repair

This is a 1x-only repair pack after the user reported V18 opened/rendered but had Bad Object Record, only one terminal, and no attached short wires.

V19 still emits through the shared terminal placer. It does not copy terminal records from the donor; it generates records from the embedded Proteus schema, but now uses catalogue facts extracted from the accepted donor: terminal label, link trailer, WIRE order, and WIRE coordinates.

Proteus open/render status: pending user test. Static validation is not Proteus acceptance.

## Files to test
- `experiments/three_pin_control_terminal_v19_donor_wire_shape_temp_2026_07_09/01_terminalized_sa/R001_POT_HG_1x_DONOR_WIRE_SHAPE_sa.pdsprj`
- `experiments/three_pin_control_terminal_v19_donor_wire_shape_temp_2026_07_09/01_terminalized_sa/R002_LM317T_1x_DONOR_WIRE_SHAPE_sa.pdsprj`
- `experiments/three_pin_control_terminal_v19_donor_wire_shape_temp_2026_07_09/01_terminalized_sa/R003_OPAMP_1x_DONOR_WIRE_SHAPE_sa.pdsprj`

## Static checks included

- no-terminal base generated from the locked new-components mega donor
- output object chunk first three bytes equal the no-terminal base
- first terminal start equals `len(no-terminal-base-chunk) - 1` and matches the curated donor
- terminal labels and terminal link trailers match accepted donor order
- WIRE coordinates and WIRE order match accepted donor evidence
- terminal symbol coordinate/angle multiset matches the curated terminalized donor evidence
