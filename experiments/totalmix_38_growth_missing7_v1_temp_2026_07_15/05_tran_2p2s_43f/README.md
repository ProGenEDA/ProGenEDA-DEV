# 38-family mixed expansion - TRAN-2P2S

This pack grows the committed 42-family baseline by exactly one four-pin
`TRAN-2P2S` transformer. It is freshly placed by the locked mega component
placer and terminalized through the existing shared placer; no donor packet,
slot, coordinate, or CDB row is reused at runtime.

- `G01_42F_PLUS_TRAN_2P2S_BARE_1X.pdsprj` - compact placed 43-family control.
- `G02_42F_PLUS_TRAN_2P2S_TERMINALIZED_1X_sa.pdsprj` - shared placer output.
- `02_local_proteus_gate/` - normal/cold delayed-open screenshots. The
  disposable gate copy is intentionally excluded from source evidence.

The visual-only compact shelf fronts `TRAN-2P2S` while preserving the placed
ROOT.DSN component stream. Static validation found 43 selected packets, 213
active terminal/WIRE units, grid-aligned terminal contacts, nonzero exact-pin
wires, final-address-rebased terminal/component suffix links, and final
`FF FF` object termination.

The transformer uses the donor-proven unit order `TOPRIGHT`, `BOTTOMRIGHT`,
`TOPLEFT`, `BOTTOMLEFT`, with `0,0,1800,1800` terminal angles and active
`0200` link trailers. The donor's final bottom-left wire has an interior bend;
the fresh grid-aligned placement is collinear there, so the shared planner
emits the equivalent nonzero direct segment rather than copying donor geometry.
Normal and cold local Proteus opens passed with no modal error or copy hash
mutation; no Ctrl+S was used. User visual review remains the final layout
authority.
