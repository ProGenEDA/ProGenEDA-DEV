# 38-family mixed expansion — 74HC74

This pack grows the committed 40-family baseline by one `74HC74` package.

- `G01_40F_PLUS_74HC74_BARE_1X.pdsprj` — compact placed control.
- `G02_40F_PLUS_74HC74_TERMINALIZED_1X_sa.pdsprj` — shared unified-terminal-
  placer result.
- `02_local_proteus_gate/` — normal/cold delayed-open evidence.

The front visual slot is the 74HC74 package, with its A and B subparts spread
and terminalized independently. Static validation found 41 components and 205
grid-aligned, nonzero terminal/WIRE pairs. The local Proteus normal/cold gate
passed with no modal dialog or copy mutation; no Ctrl+S was used.
