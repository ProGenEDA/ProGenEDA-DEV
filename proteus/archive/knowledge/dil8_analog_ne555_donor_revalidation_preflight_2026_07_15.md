# NE555 donor revalidation preflight - 2026-07-15

Authoritative terminal donor:
`proteus_ic/donors/terminalized_catalogue_evidence/dil8_analog_ic/NE555/NE555_terminalized_primary.pdsprj`.

Locked placement donor:
`proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`.

## Complete donor audit

The archive contains `SCRIPTS/PWRRAILS.DAT` (17 bytes), `ROOT.CDB` (300
bytes), `ROOT.DSN` (67,552 bytes), and `PROJECT.XML` (249 bytes). Its CDB
identifies U1 as NE555, `555.MDF`, DIL08, with R/4, DC/7, Q/3, GND/1,
VCC/8, TR/2, TH/6, and CV/5.

The DSN object chunk begins at 64,974, has 1,681 bytes, prefix
`0010d01980ff20445500000000000924`, and one explicit final `FF`. It holds
eight zero-length terminal/WIRE grammar units in order `3, 7, 6, 1, 8, 4, 5,
2`: Q, DC, TH, GND, VCC, R, CV, TR.

The component marker anchor is `(-9906000, 4572000)`. Output/DC/TH are right
side at +1270000 with y offsets +1016000/+508000/-1016000. Reset/CV/trigger
are left at -1270000 with +1016000/0/-1016000. Supply contacts GND/VCC use
left orientation at 0/-1778000 and 0/+1778000. The existing locked-mega
identity-preserving profile matches that geometry, order, labels, grammar,
direct computed WIRE rule, final address links, and explicit single-FF policy.
No profile/donor difference remains unexplained.

## Planned proof

Generate shared native-contact, grid-contact, and complete 1x stages; gate
each normally and cold. If accepted, generate/gate 9x and 15x requiring
8/72/120 grid-aligned nonzero terminal/WIRE pairs and correct final links.

## Result

Native-contact, grid-contact, and complete 1x passed normal/cold local
Proteus gates with unchanged disposable copies. Complete 9x and 15x passed
both gates. They contain 72 and 120 active terminal/WIRE pairs, every contact
is grid aligned, and every WIRE is nonzero. The 15x capture visibly retains
the reset, output, discharge, trigger, threshold, control, and supply pins.

Focused NE555 regression: `3 passed, 248 deselected`. No source or profile
change was required; user visual acceptance remains separate.
