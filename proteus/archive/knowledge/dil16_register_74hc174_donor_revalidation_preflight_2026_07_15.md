# 74HC174 donor revalidation preflight - 2026-07-15

Authoritative terminal donor:
`proteus_ic/donors/terminalized_catalogue_evidence/dil16_register/74HC174/74HC174_terminalized_primary.pdsprj`.

Locked placement donor:
`proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`.

## Complete donor audit

The archive contains `SCRIPTS/PWRRAILS.DAT` (17 bytes), `ROOT.CDB` (355
bytes), `ROOT.DSN` (68,948 bytes), and `PROJECT.XML` (249 bytes). `ROOT.CDB`
identifies U1 as 74HC174, `74XX174.MDF`, DIL16, TTLHC. It exposes D0/3,
D1/4, D2/6, D3/11, D4/13, D5/14, Q0/2, Q1/5, Q2/7, Q3/10, Q4/12,
Q5/15, CLK/9, and MR/1; VCC/16 and GND/8 are hidden.

The object chunk starts at absolute byte 65,370, is 2,681 bytes, starts
`0010d01980ff70657000000000000924`, and ends in one explicit `FF`. It
contains fourteen terminal/WIRE attachment units. The donor terminal order is
`2, 5, 7, 10, 12, 15, 3, 4, 6, 11, 13, 14, 9, 1`, labelled Q0-Q5,
D0-D5, CLK, and MR in that order. Six right-side Q terminals have 0 angle;
all eight left-side D/CLK/MR terminals have 1800. All fourteen donor WIREs
are zero-length two-point grammar records.

The 74HC174 component anchor is `(-10668000, 7620000)`. The left pin x
offset is -508000 and the right pin x offset is +2032000. From top to bottom
the data/output pairs are at y offsets -254000, -508000, -762000,
-1016000, -1270000, and -1524000; CLK is -2032000 and MR -2286000.
The catalogue profile matches the donor’s marker-relative frame, labels,
sides, record order, terminal-leading component/WIRE grammar, direct
computed grid-contact WIRE policy, and explicit single-FF finalizer. No
unexplained structural difference remains.

## Planned proof

Use only the shared component placer and shared terminal placer to generate
native-contact, grid-contact, and complete 1x outputs. Gate each normally and
cold; then generate/gate 9x and 15x only if all stages pass. Require
14/126/210 terminal/WIRE pairs, 50-unit-grid contacts, nonzero direct WIREs,
and final-address suffix links.

## Result

Native-contact, grid-contact, and complete 1x all passed normal/cold local
Proteus gates with unchanged disposable copies. Complete 9x and 15x passed the
same gates. They contain 126 and 210 active terminal/WIRE pairs; every contact
is grid aligned and every WIRE is nonzero. The captured 15x schematic shows
all data/output pairs plus clock/reset terminals in the intended positions.

Focused 74HC174 regression: `3 passed, 248 deselected`. No source or profile
change was required; user visual acceptance remains separate.
