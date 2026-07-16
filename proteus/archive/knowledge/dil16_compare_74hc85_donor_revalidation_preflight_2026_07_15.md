# 74HC85 donor revalidation preflight - 2026-07-15

Authoritative terminal donor:
`proteus_ic/donors/terminalized_catalogue_evidence/dil16_arithmetic_compare/74HC85/74HC85_terminalized_primary.pdsprj`.

Locked placement donor:
`proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`.

## Complete donor audit

The donor contains `SCRIPTS/PWRRAILS.DAT` (17 bytes), `ROOT.CDB` (351 bytes),
`ROOT.DSN` (69,220 bytes), and `PROJECT.XML` (249 bytes). The CDB identifies
U1 as 74HC85, `74XX85.MDF`, DIL16, TTLHC and includes A0/10, A1/12, A2/13,
A3/15, B0/9, B1/11, B2/14, B3/1, A<B/2, A=B/3, A>B/4, QA<B/7,
QA=B/6, QA>B/5. VCC/16 and GND/8 are hidden.

The DSN object chunk begins at 65,647, is 2,676 bytes, starts
`0010c07a93ff50245900000000000924`, and has one explicit final `FF`.
Fourteen zero-length terminal/WIRE grammar records appear in terminal order
`7, 6, 5, 10, 12, 13, 15, 9, 11, 14, 1, 2, 3, 4`: comparison outputs
QA<B/QA=B/QA>B, four A inputs, four B inputs, and three cascade inputs.

The marker anchor is `(-9906000, 8128000)`. All eleven inputs are left side
with 1800 and a -508000 x offset; the three outputs are right side with 0 and
a +2540000 x offset. The per-pin y offsets held in the catalogue reproduce the
full donor geometry (A -254000 through -1016000, B -1270000 through
-2032000, cascade -2286000 through -2794000, and right outputs -2286000
through -2794000). The current profile matches the donor’s coordinates,
ordering, labels, grammar, direct computed WIRE route, link allocation, and
single-FF ending. No unexplained difference remains.

## Planned proof

Generate shared-placer native-contact, grid-contact, and complete 1x outputs;
gate all normal/cold. If accepted, generate and gate 9x/15x. Require
14/126/210 grid-aligned nonzero terminal/WIRE pairs and final-address links.

## Result

Native-contact, grid-contact, and complete 1x passed normal/cold local
Proteus gates with unchanged disposable copies. Complete 9x and 15x passed
both gates. Each output has 14/126/210 active terminal/WIRE pairs as
appropriate, with grid-aligned contacts and nonzero direct WIREs. The 15x
capture retains all cascade inputs and comparison outputs at each component.

Focused 74HC85 regression: `3 passed, 248 deselected`. No source or profile
change was required; user visual acceptance remains separate.
