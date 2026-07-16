# 4027 shared short-WIRE retry — 2026-07-13

This is the next DSN-only 1× proof after the saved recovery boundary. It uses
the locked mega component placer, the shared catalogue terminal placer, and
the opt-in complete visible component frame. No terminal-placement script was
created for this retry.

Open in this exact order:

1. `S02_4027_1X_SHORT_WIRE_NO_TERMINAL.pdsprj`
2. `S02_4027_1X_STAGE1_NATIVE_CONTACT_sa.pdsprj`
3. `S02_4027_1X_STAGE2_OUTWARD_GRID_CONTACT_sa.pdsprj`
4. `S02_4027_1X_CATALOGUE_TERMINAL_SHORT_WIRE_sa.pdsprj`

The stages make one controlled DSN change at a time:

- Stage 1 adds fourteen inactive terminals at exact current pin contacts.
- Stage 2 moves their attaching contacts one 254000-unit grid step outward;
  there are still no WIRE records or active links.
- Stage 3 adds fourteen nonzero, donor-shaped `WIRE` records from each
  grid-aligned terminal contact to the exact pin and rebases active terminal
  and component links from final `ROOT.DSN` addresses.

Static checks confirm 14 terminals, 14 nonzero WIREs, grid-aligned terminal
contacts, exact WIRE endpoint contacts, the A/B donor block order, and a
single `FF` stream finalizer. Normal opens must remain unsaved. If a `Bad
Object Record` dismisses and opens, save only that disposable copy and compare
its `ROOT.DSN` stream.
