# DIL16 dual JK terminal v2 — 2026-07-13

## S02 4027 1x

`S02_4027_1X_NO_TERMINAL.pdsprj` is a component-placer plus beautifier
control. `S02_4027_1X_CATALOGUE_TERMINAL_sa.pdsprj` is emitted only through
the shared `component_terminal_placer.py` and the 4027 catalogue profile.

The requested `terminal_grid_alignment` layout option keeps native 4027 pin
frames on the Proteus 254000-unit terminal grid before terminal placement. The
terminal stream has 14 donor-labelled bidirectional terminals and 14
donor-shaped zero-length native WIRE units; both physical subparts are present.

Static DSN validation passed. Local Proteus cold-open/cold-reopen remains
pending because the user's existing Proteus window was deliberately not closed
or interrupted. A normal open will not be saved; only a dismissed Bad Object
Record would trigger a disposable-copy save-and-compare check.
