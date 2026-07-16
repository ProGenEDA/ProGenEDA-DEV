# 74HC192 donor revalidation preflight - 2026-07-15

Authoritative terminal donor:
`proteus_ic/donors/terminalized_catalogue_evidence/dil16_counter/74HC192/74HC192_terminalized_primary.pdsprj`.

Locked placement donor:
`proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`.

## Complete donor audit

The donor archive contains `SCRIPTS/PWRRAILS.DAT` (17 bytes), `ROOT.CDB`
(356 bytes), `ROOT.DSN` (68,902 bytes), and `PROJECT.XML` (249 bytes).
`ROOT.CDB` contains U1, 74HC192, `74XX192.MDF`, DIL16, and TTLHC. It exposes
D0/15, D1/1, D2/10, D3/9, UP/5, DN/4, PL/11, MR/14, Q0/3, Q1/2,
Q2/6, Q3/7, TCU/12, and TCD/13; VCC/16 and GND/8 are hidden.

The DSN object chunk begins at absolute byte 65,323, is 2,682 bytes, starts
with `001030da87ffd0257800000000000924`, and ends with one explicit `FF`.
It contains fourteen `$TERBIDIR` records and fourteen zero-length two-point
WIRE records. The active donor terminal order is `3, 2, 6, 7, 12, 13, 15,
1, 10, 9, 5, 4, 11, 14`; its terminal labels respectively are `Q0 PIN 3`,
`Q1 PIN 2`, `Q2 PIN 6`, `Q3 PIN 7`, `TCU PIN 12`, `TCD PIN 13`,
`D0 PIN 15`, `D1 PIN 1`, `D2 PIN 10`, `D3 PIN 9`, `UP PIN 5`,
`DN PIN 4`, `PL PIN 11`, and `MR PIN 14`.

The component marker anchor is 74HC192 at `(-10160000, 8128000)`. All left
pins have 1800 orientation and a relative x of -508000; all right pins have
0 orientation and a relative x of +2032000. Relative y values are catalogued
from the donor: Q0/D0 -254000, Q1/D1 -508000, Q2/D2 -762000,
Q3/D3 -1016000, TCU/UP -1524000, TCD/DN -1778000, PL -2032000, and
MR -2286000. Each WIRE suffix agrees with
`(absolute_object_start + wire_marker_offset - 24) & 0xffff`; source terminal
suffixes are historical and are therefore not reused by the emitter.

The zero-length donor WIREs are attachment grammar evidence. The existing
74HC192 profile already agrees with every needed fact: marker-relative
coordinates, catalogue-leading component/WIRE ordering, computed one-step
outward grid contacts, direct terminal-contact-to-exact-pin WIREs, final
address suffix allocation, and `append_explicit_single_ff`. No unexplained
profile-vs-donor difference remains and no shared placer or profile change is
planned.

## Planned proof

Create locked-mega native-contact, grid-contact, and complete 1x diagnostics;
gate all three normally and cold. Only if those pass, create complete 9x and
15x outputs and gate both. Require 14/126/210 terminal/WIRE pairs, every
terminal contact on the 50-unit grid, nonzero direct WIREs to exact pins,
final-address suffix links, and the family-specific single-FF policy.

## Result

All native-contact, grid-contact, and complete 1x diagnostics passed normal
and cold local Proteus gates with unchanged disposable copies. The complete 9x
and 15x outputs passed the same gates. They contain 126 and 210 terminal/WIRE
pairs respectively; every contact is on the 50-unit grid and every WIRE is
nonzero. The recorded 15x screen shows terminalized counters in the expected
two-sided arrangement.

Focused counter regression: `6 passed, 47 deselected`. No source or catalogue
profile change was required; user visual acceptance remains separate.
