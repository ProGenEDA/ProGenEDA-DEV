# 4511 donor revalidation preflight - 2026-07-15

Authoritative terminal donor:
`proteus_ic/donors/terminalized_catalogue_evidence/dil16_decoder_driver/4511/4511_user_terminalized_july04.pdsprj`.

Locked placement donor:
`proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`.

## Complete donor audit

The archive has `SCRIPTS/PWRRAILS.DAT` (17 bytes), `ROOT.CDB` (350 bytes),
`ROOT.DSN` (109,773 bytes), and `PROJECT.XML` (249 bytes). `ROOT.CDB` has one
`U9` pin row and one property row: `4511`, `4511.MDF`, `DIL16`, 5 V CMOS.
Visible pins are A 7, B 1, C 2, D 6, LT 3, BI 4, LE/STB 5 and QA-QG
13/12/11/10/9/15/14; VDD 16 and VSS 8 are hidden.

The DSN object chunk begins at absolute byte 106,232, is 2,644 bytes, and has
the donor-proven explicit final `FF`. It contains fourteen terminal/WIRE
attachment units in component-stream-then-attachment order. Terminal order:

`PIN13QA, PIN12QB, PIN11QC, PIN10QD, PIN9QE, PIN15QF, PIN14QG, PIN7A,
PIN1B, PIN2C, PIN6D, PIN3LT, PIN4BI, PIN5LE/NSTB`.

All fourteen WIREs are nonzero two-point routes. Right-side terminals use 0
and left-side terminals use 1800. Each route starts/ends at a grid-aligned
terminal contact and an exact off-grid pin point. The active suffix is the low
16 bits of the absolute byte immediately before its WIRE marker; catalogue
link positions and `01 00` trailers are donor evidence.

The current profile uses donor-explicit terminal contacts, donor-coordinate
routes retargeted to current component coordinates, catalogue-leading WIRE
records, and an explicit finalizer. This is potentially similar to the 74HC151
endpoint-selection risk, so a fresh complete 1x output must be audited before
any scale generation. No source/profile change is justified from this audit
alone.

## Planned proof

Generate 1x control/native/grid/complete through the shared placer, compare
every complete WIRE's contacts and nonzero state against the current component,
and gate all stages normally/cold. Only then generate 9x/15x. A repair, if
needed, must be profile-local and preserve all frozen accepted families.

## Result

The existing 4511 profile passed without modification. Its fresh complete 1x
output preserved fourteen nonzero donor-shaped two-point WIRE paths. Native,
grid, and complete 1x diagnostics plus complete 9x/15x finals normal-opened
and cold-reopened after the required delay with no modal error or disposable-
copy mutation. Final outputs have 14/126/210 grid-aligned contacts, nonzero
exact-pin wires and matching final-address links. The 15x screenshot visibly
shows repeated terminalized decoder packages. Focused 4511 regression: 3
passed. User visual acceptance remains separate.
