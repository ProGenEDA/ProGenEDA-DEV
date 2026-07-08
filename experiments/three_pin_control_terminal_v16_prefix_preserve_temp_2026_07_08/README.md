# Three-pin control terminal V16 prefix-preserve repair

This is a 1x-only repair pack for the V15 empty-sheet failure.

Root cause fixed in the shared terminal placer: V15 rebuilt the object stream from `original_chunk[:1]` plus local records and dropped byte 1 of the component packet (`08` for POT-HG, `00` for LM317T/OPAMP). V16 preserves that byte before the first component packet.

Proteus open/render status: pending user test. Static validation is not Proteus acceptance.

## Files to test
- `experiments/three_pin_control_terminal_v16_prefix_preserve_temp_2026_07_08/01_terminalized_sa/R001_POT_HG_1x_PREFIX_PRESERVE_sa.pdsprj`
- `experiments/three_pin_control_terminal_v16_prefix_preserve_temp_2026_07_08/01_terminalized_sa/R002_LM317T_1x_PREFIX_PRESERVE_sa.pdsprj`
- `experiments/three_pin_control_terminal_v16_prefix_preserve_temp_2026_07_08/01_terminalized_sa/R003_OPAMP_1x_PREFIX_PRESERVE_sa.pdsprj`

## Static checks included

- no-terminal base generated from the locked new-components mega donor
- output object chunk first three bytes equal the no-terminal base
- component packet appears before terminal/WIRE attachment units
- terminal symbol coordinate/angle multiset matches the curated terminalized donor evidence
