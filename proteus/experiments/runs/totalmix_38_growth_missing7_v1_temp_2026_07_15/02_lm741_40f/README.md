# 38-family mixed expansion — LM741

This pack grows the committed 39-family NE555 baseline by one family only:
`LM741`.

- `G01_39F_PLUS_LM741_BARE_1X.pdsprj` — compact placed control.
- `G02_39F_PLUS_LM741_TERMINALIZED_1X_sa.pdsprj` — shared unified terminal-
  placer output.
- `02_local_proteus_gate/` — normal/cold delayed-open evidence.

The test-only layout uses a 50,000,000-unit compact shelf and fronts LM741 at
visual slot zero without changing component packet order. Static validation
found 40 selected components, 193 active terminal/WIRE pairs, grid-aligned
terminal contacts, and nonzero endpoint-valid WIREs.

LM741 donor order is retained exactly: terminals `6,1,7,5,4,3,2`; WIREs
`3,2,6,7,4,1,5`. The local normal/cold Proteus gate passed with no modal error
or copy mutation; no Ctrl+S was used. User visual review remains separate.
