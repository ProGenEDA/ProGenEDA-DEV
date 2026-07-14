# 4027 donor revalidation preflight — 2026-07-14

Authoritative donor:
`proteus_ic/donors/terminalized_catalogue_evidence/dil16_dual_jk_ff/4027/4027_terminalized_primary.pdsprj`.
The only placement source is the locked
`proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`.

## Complete donor contents

The archive contains `SCRIPTS/PWRRAILS.DAT` (17 bytes), `ROOT.CDB` (364 bytes),
`ROOT.DSN` (69,878 bytes), and `PROJECT.XML` (249 bytes). The CDB has the two
subpart pin rows (`U1:A`, `U1:B`) and one package property row (`U1`).

The 3,018-byte object chunk begins at absolute `65963`, has fourteen
`$TERBIDIR` records, fourteen WIRE records, two component subparts, and one
final `FF`. Its exact donor block topology is:

`A terminals (1,2,4,6,3,5,7) → U1:A → A WIREs (6,1,3,5,2,7,4)`

`B terminals (15,14,12,10,13,11,9) → U1:B → B WIREs (10,15,13,11,14,9,12)`.

All donor WIREs are zero length because their contacts coincide with native
pin locations. That proves the binary block/link grammar only; it is not the
final routing geometry required by the shared terminal contract.

## Current-emitter finding

The current catalogue already correctly carries the two subpart anchors,
pin-relative geometry, subpart-end link slots, terminal order, and CDB
preservation policy. A fresh plan showed one remaining error: its final WIRE
coordinates still copied the donor's zero-length pin-to-pin coordinates, while
the planned terminal contact was a distinct grid coordinate. That leaves a
visible terminal unconnected.

The evidence-backed repair is bounded to this catalogue profile: retain the
donor-explicit grid terminal contact and change only WIRE geometry to the
shared `computed_terminal_contact_to_pin` policy. The native diagnostic still
uses a coincident zero-length unit; the grid/final stages use a nonzero short
WIRE from that same grid contact to the untouched exact pin. The donor's active
terminal/component-link/WIRE unit is loader-required, so staged diagnostics
must use the profile's active attachment unit rather than detached terminals.

## Corrected final-contact finding and gate results

The first regenerated final profile still inherited each donor's explicit
contact coordinates. For 4027 those coordinates are the already grid-aligned
exact pin endpoints, so every resulting final WIRE was zero length. That is a
valid donor diagnostic grammar but not the accepted final terminal contract.

The bounded catalogue correction is therefore `computed_outward_grid` with one
254,000-unit grid step and `computed_terminal_contact_to_pin`. It does not
change the component packets, relative pin geometry, subpart ordering, link
slots, CDB policy, or any other family. The shared placer now produces a
one-grid horizontal WIRE from each grid-aligned terminal contact to its exact
pin: fourteen per package, with left pins at 1800 and right pins at 0.

Fresh local Proteus gates on 2026-07-15 passed normal open and cold reopen with
unchanged disposable-copy hashes and no modal loader dialogs:

- `C02_4027_NATIVE_PIN_CONTACT_sa.pdsprj`: native active-unit diagnostic.
- `C03_4027_GRID_CONTACT_sa.pdsprj`: 14 nonzero grid-contact WIREs.
- `C04_4027_CATALOGUE_TERMINAL_sa.pdsprj`: 14 nonzero final WIREs.
- `S09_4027_9X_COMPLETE.pdsprj`: 126 nonzero final WIREs.
- `S15_4027_15X_COMPLETE.pdsprj`: 210 nonzero final WIREs; the pre-close
  capture shows repeated terminalized 4027 symbols without a loader dialog.

The native diagnostic retains zero-length WIREs only to prove the donor's
loader-required active attachment unit. It is not a terminal handoff route.
