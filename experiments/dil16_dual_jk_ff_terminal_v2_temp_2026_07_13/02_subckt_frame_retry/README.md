# 4027 DSN-only subcircuit-frame retry — 2026-07-13

This retry keeps the same locked-mega component-placer route and shared
`component_terminal_placer.py` route. It changes only the additive,
terminal-grid opt-in component-frame repair: both physical 4027 `SUBCKT NAME`
label coordinate pairs now move with their corresponding component body.

Test these in order:

1. `S02_4027_1X_SUBCKT_FRAME_NO_TERMINAL.pdsprj`
2. `S02_4027_1X_STAGE1_NATIVE_CONTACT_sa.pdsprj`
3. `S02_4027_1X_STAGE2_GRID_CONTACT_sa.pdsprj`
4. `S02_4027_1X_CATALOGUE_TERMINAL_SUBCKT_FRAME_sa.pdsprj`

Stages 1 and 2 contain fourteen inactive terminals and no WIRE records.
Stage 3 adds fourteen donor-shaped active WIRE/link units. The terminal stage
reads and writes `ROOT.DSN` only. A normal open must not be saved. If Proteus
shows `Bad Object Record` but then opens, dismiss it, save only that disposable
copy, and compare its `ROOT.DSN` recovery delta.

The user-saved `fixS02_4027_1X_CATALOGUE_TERMINAL_sa.pdsprj` is retained in
the previous folder as evidence of the original recovery boundary; it is not a
complete terminalized 4027 output.
