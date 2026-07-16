# 74HC76 donor revalidation - 2026-07-13

## Scope

The accepted primary donor is
`proteus_ic/donors/terminalized_catalogue_evidence/dil16_dual_jk_ff/74HC76/74HC76_terminalized_primary.pdsprj`.
The placement source remains the locked new-components mega donor. Per the
user's DSN-only instruction for this repair sequence, this note compares
`ROOT.DSN` only and does not use `ROOT.CDB` as an emitter
source or comparison target.

## Complete attachment-stream facts

The donor has a 3,042-byte object stream with:

- 14 `$TERBIDIR` records;
- two physical 74HC76 component records, `U1:A` and `U1:B`;
- 14 active WIRE records;
- one final `FF` byte.

Its stream is intentionally asymmetric:

`12 terminals -> A component -> 7 WIREs -> 2 terminals -> B component -> 7 WIREs -> FF`

All WIRE records have equal endpoints at the donor-proven terminal grid
contact. The first A/B WIRE marker offsets are 1741 and 2715, respectively;
each is 431 bytes after its donor component marker. Terminal angles, labels,
pin order, active component-link suffixes, and the asymmetric block order are
catalogue facts that must remain unchanged.

## Locked-mega 1x regeneration

The shared placer selected `U41:A/B` from the locked mega and produced
`S03_74HC76_1X_CATALOGUE_TERMINAL_sa.pdsprj`. Because `U41`
is one character wider than donor `U1`, its A/B first WIRE marker
distances are correctly 432 bytes. The output's marker offsets are:

- A: 1742;
- B: 2717.

Actual DSN parsing verifies 14 terminals, 14 active WIREs, equal grid-aligned
endpoints, unique suffixes, correct finalizer, and both physical references.

## Local gate

The regenerated 1x reached the normal Proteus Schematic Capture window on
visible cold open and foregrounded cold reopen, with no modal error. Screens
captured before closing:

- `09_hc76_donor_revalidation/G16_74HC76_1X_BEFORE_CLOSE.png`;
- `09_hc76_donor_revalidation/G17_74HC76_1X_COLD_REOPEN_BEFORE_CLOSE.png`.

Normal opens were not Ctrl+S-saved. This validates the frozen 74HC76 profile
as the next group member; any scale pack must invoke that same shared profile
without changing 4027 or accepted two-pin routes.
