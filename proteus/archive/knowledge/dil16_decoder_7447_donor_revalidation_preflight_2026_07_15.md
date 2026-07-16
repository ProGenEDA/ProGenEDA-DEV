# 7447 donor revalidation preflight - 2026-07-15

Authoritative terminal donor:
`proteus_ic/donors/terminalized_catalogue_evidence/dil16_decoder_driver/7447/7447_terminalized_primary.pdsprj`.

Locked placement donor:
`proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`.

## Complete donor audit

The archive members are `SCRIPTS/PWRRAILS.DAT` (17 bytes), `ROOT.CDB` (337
bytes), `ROOT.DSN` (69,183 bytes), and `PROJECT.XML` (249 bytes). `ROOT.CDB`
contains one `U1` pin row and property row: 7447, `74XX47.MDF`, DIL16, TTL.
Visible pins are A/B/C/D 7/1/2/6; QA-QG 13/12/11/10/9/15/14; BI/RBO 4,
RBI 5, LT 3. VCC 16 and GND 8 are hidden.

The DSN object chunk starts at absolute byte 65,676, has length 2,610, and
uses the donor-proven explicit final `FF`. It contains fourteen terminal/WIRE
records in this order:

`QA PIN 13, QB PIN 12, QC PIN 11, QD PIN 10, QE PIN 9, QF PIN 15,
QG PIN 14, A PIN 7, B PIN 1, C PIN 2, D PIN 6, BI/RBO PIN 4, RBI PIN 5,
LT PIN 3`.

All donor WIREs are two-point zero-length attachment units. They establish
record/link ordering, suffix address allocation, and component-link grammar,
not final visual wire geometry. Terminals are 0 on the right and 1800 on the
left. The historical 7447 coordinate issue means every fresh final must be
checked against current component anchors and grid contacts, rather than only
against absolute donor coordinates.

The existing profile already selects one outward grid step plus
`computed_terminal_contact_to_pin`, catalogue-leading records, and an explicit
finalizer. No profile or shared-emitter change is justified unless fresh output
or the local gate proves a discrepancy.

## Planned proof

Generate native/grid/complete 1x diagnostics from the locked mega, then
normal/cold gate them. Only a passing 1x permits 9x/15x. Complete routes must
contain 14/126/210 grid-aligned nonzero terminal-to-exact-pin wires and
final-address suffix links. No alternate terminal workflow is permitted.

## Result

The existing profile passed without modification. Fresh final 1x/9x/15x
outputs have 14/126/210 grid-aligned terminal contacts and nonzero direct
two-point WIREs with matching final-address links. Native, grid, and complete
1x diagnostics plus complete 9x/15x finals normal-opened and cold-reopened
after the required delay without a loader dialog or disposable-copy mutation.
The 15x screenshot shows the expected pin-adjacent terminal layout. Focused
7447 regression: 3 passed. User visual acceptance remains separate.
