# BJT 1x Proteus-opened recovery — 2026-07-11

This pack contains one terminalized solo each for `NPN`, `PNP`, `2N3904`, and
`2N4401`, generated through the locked-mega component placer and the shared
`component_terminal_placer.py`.

The terminal stage now normalizes `ROOT.CDB` to the selected component packages
after emitting active terminal/component-pin links. This matches Proteus's
Ctrl+S behavior and fixes the stale mega-CDB property count that caused the
previous BJT loader failures.

## Local Proteus result

Every `*_sa.pdsprj` passed all of the following locally in Proteus 8:

1. cold launch with no `Fatal Error`, `LXLCORE`, `Bad Object Record`, or
   device-library modal dialog;
2. an additional ten-second post-load dialog check;
3. Ctrl+S with no project hash change;
4. process termination and cold reopen of the saved copy.

The result is recorded in `live_proteus_gate.json`. The captured canvas image
path is deliberately not an acceptance signal: the same capture method shows a
blank canvas for the authoritative accepted NPN donor, so it cannot distinguish
layout correctness. Inspect these four in normal interactive Proteus for final
visual confirmation.

`2N3904` and `2N4401` currently use donor aliases that contain NPN terminal
geometry; their generated native packets are still independently placed and
were independently opened, saved, and cold-reopened.
