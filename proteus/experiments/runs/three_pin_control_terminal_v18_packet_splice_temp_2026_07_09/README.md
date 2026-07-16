# Three-pin control terminal V18 packet-splice repair

This is a 1x-only repair pack for the V16/V17 faulty-output rejection.

V16 appended terminal/WIRE units after the selected component packet. V17 matched the first-terminal boundary but incorrectly moved the selected packet's stale final byte to the end. V18 drops that stale selected byte and lets the final object-stream terminator be emitted normally.

Proteus open/render status: pending user test. Static validation is not Proteus acceptance.

## Files to test
- `experiments/three_pin_control_terminal_v18_packet_splice_temp_2026_07_09/01_terminalized_sa/R001_POT_HG_1x_PACKET_SPLICE_sa.pdsprj`
- `experiments/three_pin_control_terminal_v18_packet_splice_temp_2026_07_09/01_terminalized_sa/R002_LM317T_1x_PACKET_SPLICE_sa.pdsprj`
- `experiments/three_pin_control_terminal_v18_packet_splice_temp_2026_07_09/01_terminalized_sa/R003_OPAMP_1x_PACKET_SPLICE_sa.pdsprj`

## Static checks included

- no-terminal base generated from the locked new-components mega donor
- output object chunk first three bytes equal the no-terminal base
- first terminal start equals `len(no-terminal-base-chunk) - 1` and matches the curated donor
- selected packet's stale final byte is not moved after terminal/WIRE units
- component packet appears before terminal/WIRE attachment units
- terminal symbol coordinate/angle multiset matches the curated terminalized donor evidence
