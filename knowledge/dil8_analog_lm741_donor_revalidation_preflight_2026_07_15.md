# LM741 donor revalidation preflight - 2026-07-15

Authoritative terminal donor:
`proteus_ic/donors/terminalized_catalogue_evidence/dil8_analog_ic/LM741/LM741_terminalized_primary.pdsprj`.

Locked placement donor:
`proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`.

## Complete donor audit

The donor archive includes `SCRIPTS/PWRRAILS.DAT` (17 bytes), `ROOT.CDB`
(358 bytes), `ROOT.DSN` (67,880 bytes), and `PROJECT.XML` (249 bytes). The
CDB identifies U1 as LM741, DIL08, analogue subcircuit, and exposes +IP/3,
-IP/2, OP/6, V+/7, V-/4, OFFSET1/1, and OFFSET2/5.

The object chunk begins at 65,435, has 1,548 bytes, prefix
`0010d01980ffe0c46400000000000924`, and a single explicit final `FF`. It
contains seven zero-length terminal/WIRE grammar units in order `6, 1, 7, 5,
4, 3, 2`. Its marker anchor is `(-9652000, 6604000)`: output 6 is right at
+1016000/0; offsets 1 and 5 are right at 0/+1016000 and 0/-1016000; supplies
7/4 are left at -254000/+1016000 and -254000/-1016000; inputs 3/2 are left at
-1016000/+254000 and -1016000/-254000. All seven donor WIREs are zero-length
two-point grammar evidence.

The profile preserves the locked-mega leading component identity record, and
matches the donor frame/order and terminal-leading component/WIRE grammar. It
uses grid-snapped terminal contacts, direct WIREs, final-address links, and
an explicit single-FF finalizer. No unexplained profile/donor difference
remains.

## Planned proof

Generate native-contact, grid-contact, and complete 1x through the shared
placers and gate each normal/cold. Only then create/gate final 9x and 15x.
Require 7/63/105 grid-aligned nonzero terminal/WIRE pairs and correct
final-address link allocation.

## Result

Native-contact, grid-contact, and complete 1x passed normal/cold local
Proteus gates with unchanged disposable copies. Complete 9x and 15x passed
both gates. They contain 63 and 105 active terminal/WIRE pairs, all contact
points are grid aligned, and all WIREs are nonzero. The 15x capture visibly
shows all seven pin terminals around each op-amp.

Focused LM741 regression: `3 passed, 248 deselected`. No source or profile
change was required; user visual acceptance remains separate.
