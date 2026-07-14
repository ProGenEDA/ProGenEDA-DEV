# 74HC283 donor revalidation preflight - 2026-07-15

Authoritative terminal donor:
`proteus_ic/donors/terminalized_catalogue_evidence/dil16_arithmetic_compare/74HC283/74HC283_terminalized_primary.pdsprj`.

Locked placement donor:
`proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`.

## Complete donor audit

The donor has `SCRIPTS/PWRRAILS.DAT` (17 bytes), `ROOT.CDB` (345 bytes),
`ROOT.DSN` (69,217 bytes), and `PROJECT.XML` (249 bytes). Its CDB identifies
U1 as 74HC283, `74XX283.MDF`, DIL16, TTLHC and exposes A0/5, A1/3, A2/14,
A3/12, B0/6, B1/2, B2/15, B3/11, C0/7, C4/9, S0/4, S1/1, S2/13, and
S3/10; VCC/16 and GND/8 are hidden.

The DSN object chunk begins at 65,649, has 2,671 bytes, prefix
`0010c07a93ff70657000000000000924`, and a single explicit final `FF`. It has
fourteen zero-length terminal/WIRE grammar units in order `4, 1, 13, 10, 9,
5, 3, 14, 12, 6, 2, 15, 11, 7`: S0-S3, C4, A0-A3, B0-B3, C0.

The body anchor is `(-9398000, 7620000)`. All left-side A/B/C0 pins use 1800
and -508000 relative x; all right-side S/C4 pins use 0 and +2032000 relative
x. Their per-pin relative y positions in the existing catalogue reproduce the
complete donor geometry: outputs S0-S3 -254000/-508000/-762000/-1016000,
C4 -2794000; A0-A3 -254000/-508000/-762000/-1016000; B0-B3
-1524000/-1778000/-2032000/-2286000; C0 -2794000. The current profile
matches the donor frame, side/orientation, order, terminal-leading records,
computed grid contact, direct WIRE, address suffix allocation, and explicit
single-FF policy. No structural mismatch is unexplained.

## Planned proof

Create native-contact, grid-contact, and complete 1x diagnostics through the
shared placers; normal/cold gate each. Then create/gate 9x/15x if all 1x
stages pass. Require 14/126/210 grid-aligned active terminal/WIRE pairs,
nonzero direct WIREs, and final-address suffix links.

## Result

Native-contact, grid-contact, and complete 1x passed normal/cold local
Proteus gates with unchanged disposable copies. The 9x and 15x complete
projects passed both gates as well. They contain 126 and 210 active
terminal/WIRE pairs, all contact points are grid aligned, and every WIRE is
nonzero. The 15x capture visibly retains the A/B inputs and S/C outputs.

Focused 74HC283 regression: `3 passed, 248 deselected`. No source or profile
change was required; user visual acceptance remains separate.
