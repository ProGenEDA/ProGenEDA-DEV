# 38-family mixed expansion - BRIDGE

This pack grows the committed 41-family baseline by exactly one four-pin
`BRIDGE` component. It is freshly placed from the locked mega donor and then
terminalized through the existing shared terminal placer; no donor packet,
slot, coordinate, or CDB row is transplanted at runtime.

- `G01_41F_PLUS_BRIDGE_BARE_1X.pdsprj` - compact placed 42-family control.
- `G02_41F_PLUS_BRIDGE_TERMINALIZED_1X_sa.pdsprj` - shared placer output.
- `02_local_proteus_gate/` - normal/cold delayed-open screenshots. The
  disposable gate copy is intentionally not source evidence.

The test-only layout uses the compact 50,000,000-unit shelf and visual-only
fronting for `BRIDGE`; the placed ROOT.DSN component packet order remains
unchanged. Static validation found 42 selected packets, 209 active terminal /
WIRE units, grid-aligned terminal contacts, nonzero exact-pin wires, and
final-address-rebased terminal/component suffix links.

BRIDGE uses its complete donor-derived tail-unit order: `RIGHT`, `TOP`,
`BOTTOM`, `LEFT`. The left physical pin uses 1800 degrees; the other donor
pins use 0 degrees. The normal and cold local Proteus gate passed without a
modal error or disposable-copy hash mutation; no Ctrl+S was used. User visual
review remains the authority for final layout acceptance.
