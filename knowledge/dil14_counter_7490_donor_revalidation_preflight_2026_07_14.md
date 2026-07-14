# 7490 donor revalidation preflight — 2026-07-14

Authoritative terminal donor:
`proteus_ic/donors/terminalized_catalogue_evidence/dil14_counter/7490/7490_terminalized_primary.pdsprj`.
The locked placement source remains exclusively
`proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`.

## Complete project members

The authoritative archive contains `SCRIPTS/PWRRAILS.DAT` (17 bytes),
`ROOT.CDB` (367 bytes), `ROOT.DSN` (68,449 bytes), and `PROJECT.XML` (249
bytes). `ROOT.CDB` has one `U1` pin row and one `U1` property row; its pin
table exposes CKA/14, Q0/12, CKB/1, Q1/9, Q2/8, Q3/11, R0(1)/2, R0(2)/3,
R9(1)/6, R9(2)/7, VCC/5, and GND/10.

## ROOT.DSN object-stream evidence

The donor object chunk begins at absolute `65495`, is 2,057 bytes, contains
ten `$TERBIDIR` records and ten `WIRE` records, and ends with exactly one
explicit `FF` finalizer. The terminal record order is:

`14, 1, 2, 3, 6, 7, 12, 9, 8, 11`.

The component record starts at relative byte `1108`; its bare component span
ends at `1556` and is 448 bytes. The WIRE/link order is:

`14, 12, 1, 9, 8, 11, 2, 3, 6, 7`.

Each WIRE is the 50-byte catalogue-leading-separator form (`00` immediately
before the normal WIRE prefix). Donor WIREs are zero length only because their
terminal contacts coincide with native grid-aligned pin locations. Final output
must instead use the shared planner's grid contact and a nonzero short WIRE to
the unchanged exact pin.

The ten component link fields form a contiguous 4-byte `suffix, 01 00` array
at component-end-relative offsets `-48, -44, -40, -36, -32, -28, -24, -20,
-16, -12`, in that WIRE order. The locked-mega bare 1x component is also 448
bytes and has zeroed fields at those exact positions. Its only meaningful
donor-vs-bare differences are placement/reference coordinates and activation
of those link slots.

## Emission decision

Use the existing shared catalogue terminal placer only, with
`terminal_leading_component_then_wires`, terminal order above,
catalogue-leading WIRE encoding, `append_explicit_single_ff`, and link trailer
`0100`. No standalone 7490 terminal script, donor transplant, or component
placer replacement is permitted. The new geometry facts are a bounded 7490
catalogue addition; no accepted family geometry or emitter route is altered.

## First native-stage failure and complete correction

The first active native-contact candidate cold-opened with a `Fatal Error`.
Its terminal order, active links, WIRE count, and suffixes matched the donor,
but every WIRE started at relative byte `1557` instead of the donor's `1556`:
the component placer packet retained one raw trailing finalizer byte before
the first native WIRE. This is the same byte-boundary class already proven for
other terminal-leading packets. The complete donor-vs-generated difference is
therefore one stale trailing `00`, not a coordinate or terminal-link guess.
Set the catalogue's
`strip_component_placer_finalizer_before_terminal_leading_wires: true`, then
regenerate all three 1x diagnostic stages. This removes exactly that byte,
moves each WIRE/link allocation to the donor-relative boundary, and leaves all
accepted family paths unchanged.

## Result

The corrected active native-contact, grid-contact, and final 1x projects each
normal-opened and cold-reopened without a modal dialog or copy mutation. The
shared final route then generated and passed the same gate for 9x (90
attachments) and 15x (150 attachments). Focused 7490, HC74, and frozen
two-pin regression coverage passed with 19 tests; catalogue JSON and Python
compile checks also passed.
