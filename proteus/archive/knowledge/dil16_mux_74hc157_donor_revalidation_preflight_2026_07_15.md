# 74HC157 donor revalidation preflight - 2026-07-15

Authoritative terminal donor:
`proteus_ic/donors/terminalized_catalogue_evidence/dil16_mux/74HC157/74HC157_terminalized_primary.pdsprj`.

Locked placement donor:
`proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`.

## Complete donor audit

The archive members are `SCRIPTS/PWRRAILS.DAT` (17 bytes), `ROOT.CDB` (347
bytes), `ROOT.DSN` (69,276 bytes), and `PROJECT.XML` (249 bytes). `ROOT.CDB`
has one `U1` pin row and one property row: `74HC157`, `74XX157.MDF`, `DIL16`,
and `TTLHC`. It records visible pins `1A/1Y/1B`, `2A/2Y/2B`, `3A/3Y/3B`,
`4A/4Y/4B`, `$A$/B`, and `E`; VCC 16 and GND 8 are hidden.

`ROOT.DSN` has an object chunk at absolute byte 65,707, length 2,672, with the
donor-proven explicit final `FF`. The chunk contains fourteen terminal records
and fourteen WIRE records. Terminal order is:

`1Y PIN 4, 2Y PIN 7, 3Y PIN 9, 4Y PIN 12, 1A PIN 2, 1B PIN 3, 2A PIN 5,
2B PIN 6, 3A PIN 11, 3B PIN 10, 4A PIN 14, 4B PIN 13, NA/B PIN 1, E PIN 15`.

Every donor terminal uses 0 on the right or 1800 on the left. The fourteen
donor WIRE records are two-point but zero length. They establish attachment
order, record grammar, suffix/address allocation and component link slots; as
with the accepted 4027/74HC76 cases, they must not be replayed as final visual
attachment geometry.

The existing 74HC157 profile already declares the required final behavior:
`computed_outward_grid`, one outward grid step,
`computed_terminal_contact_to_pin`, catalogue-leading WIRE encoding, and an
explicit single-FF finalizer. No profile or shared-emitter change is justified
unless the fresh locked-mega output or local loader gate proves a discrepancy.

## Planned proof

Generate the locked-mega 1x no-terminal control, native-contact and
grid-contact diagnostics, and complete final through the shared placer. Gate
the 1x stages before generating 9x and 15x. The final route must have 14/126/
210 grid-aligned terminal contacts, nonzero short WIREs to exact pins, matching
final-address terminal/component links, selected-package CDB, and the donor
finalizer. No new terminal script or family-specific workflow is permitted.

## Result

The existing profile passed without modification. Fresh final 1x/9x/15x
outputs contained 14/126/210 grid-aligned terminal contacts and nonzero direct
two-point WIREs, with matching final-address links. Native, grid, and complete
1x diagnostics plus complete 9x/15x finals normal-opened and cold-reopened
after the required delay without a modal error or disposable-copy mutation.
The retained 15x screenshot shows repeated packages with nearby terminals.
Focused 74HC157 regression: 3 passed. User visual acceptance remains separate.
