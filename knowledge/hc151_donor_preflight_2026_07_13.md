# 74HC151 donor preflight - 2026-07-13

## Authority and scope

The authoritative accepted donor is
`proteus_ic/donors/terminalized_catalogue_evidence/dil16_mux/74HC151/74HC151_user_terminalized_july04.pdsprj`.
The locked mega remains the only component-placement donor. This initial
preflight uses `ROOT.DSN` evidence only, following the active
DSN-only repair practice; no new terminal emitter or component-specific script
is permitted.

## Complete donor stream

The 74HC151 donor has:

- a 2,687-byte object stream;
- physical reference `U49`;
- 14 terminal records;
- 14 active WIRE records;
- a final `FF` byte.

The component precedes all attachment units. Each terminal is immediately
followed by its WIRE; donor WIRE marker offsets are
569, 726, 883, 1040, 1205, 1362, 1520, 1686, 1844, 2010, 2175, 2340,
2496, and 2660.

Unlike 4027/HC76, several accepted WIREs are nonzero multi-point paths:
terminal contact is on the Proteus grid and a short donor-shaped path reaches
the exact 74HC151 pin. The profile must preserve the full donor polyline,
terminal angle (1800 left / 0 right), labels, pin link fields, and final
address rebasing. It may not replace this with a zero-length or label-only
route.

## Existing catalogue state

The current 74HC151 profile has relative pin geometry, terminal labels,
donor WIRE coordinates, role names, link-tail fields, and grid snap facts, but
does not yet declare the common high-level attachment grammar fields used by
the recent multipart profiles. The next safe action is to invoke the current
shared placer once against the locked mega, then compare every generated DSN
difference to this donor before modifying the shared placer or catalogue.

## Existing shared-profile probe: complete difference set

The first locked-mega/shared-placer probe is static-valid but is not a handoff
candidate. A complete donor-versus-probe DSN comparison found all of these
differences before any repair is made:

1. The profile still cites an older no-terminal project rather than the
   accepted user-terminalized donor.
2. Six donor WIRE records have three points, but their catalogue entries kept
   only the first two points. This removes 48 bytes from the 14-unit stream,
   shifts every later WIRE marker, and loses the donor routing topology.
3. The attachment order is currently only implicit. It must explicitly state
   component stream followed by the fourteen donor-ordered terminal/WIRE
   units.
4. The finalizer is currently implicit and becomes double-FF, while the donor
   ends in one FF.
5. The probe's transformed contacts are otherwise correctly reference/anchor
   rebased; its first four WIRE marker positions already match the donor
   before the first truncated three-point path.

The evidence-backed change set is catalogue-only: update all stale source
paths, restore all six complete coordinate paths, freeze the exact unit order,
and declare the donor single-FF finalizer. No shared placer code, accepted
family profile, or CDB path is to be changed. The regenerated DSN must then
be re-compared for any remaining difference before a loader gate.

## Regenerated packet audit: finalizer correction

After restoring every full WIRE path and the unit order, the generated object
stream matched all fourteen donor WIRE marker offsets and all donor polyline
point counts. Its only remaining difference was one byte: 2,686 bytes rather
than the donor's 2,687 bytes.

The final donor WIRE begins at offset 2660. Its final coordinate ends in
binary byte `FF`, followed by a separate structural `FF` object-stream
finalizer. The generated final coordinate also ends in `FF`, but the generic
`single_ff` normalizer treated that coordinate byte as an existing finalizer
and emitted nothing further. This is not a double-finalizer donor; it needs
the existing catalogue policy `append_explicit_single_ff`, which always adds
one structural byte after the last WIRE payload.

The 74HC151 profile therefore uses `append_explicit_single_ff`. This is an
evidence-backed per-profile finalizer selection; it does not modify the
shared emitter, any accepted family profile, or ROOT.CDB.

## Pin-target versus grid-contact correction

The first regenerated packet had the correct 2,687-byte stream and finalizer,
but the shared report rejected eight WIREs as not reaching their pin. Donor
inspection showed that the profile's stored component-relative pin coordinates
were already correct: each is the first point of its WIRE. The defect was the
legacy `pin_endpoint_snap_axes: ["y"]` setting, which snapped the *physical
pin* to the terminal grid during planning. That displaced the validation
target by 20,320 internal units.

All fourteen HC151 entries now use an empty snap-axis list. This does not move
any terminal: terminal contact coordinates remain the donor's grid-aligned
points, while the first WIRE point remains the exact, unsnapped component pin.
The fixed profile therefore follows the required mechanics:

`grid terminal contact -> donor-shaped short WIRE -> exact physical pin`.

## Final complete DSN comparison

The final locked-mega 1x output is
`experiments/dil16_mux_terminal_v1_temp_2026_07_13/05_hc151_donor_endpoint_verified/S01_74HC151_1X_CATALOGUE_TERMINAL_sa.pdsprj`.

- donor and generated object streams are both 2,687 bytes;
- both have fourteen terminals, fourteen WIREs, the same labels, angles,
  terminal coordinates, WIRE marker offsets, and complete WIRE polylines;
- both end in the same final 27-byte final-WIRE-plus-structural-FF payload;
- all terminal contacts are on the 254,000-unit grid and every WIRE reaches
  its exact physical pin;
- the only byte differences are 56 bytes: the fourteen terminal suffixes and
  their fourteen component link fields, each rebased from its final ROOT.DSN
  WIRE address.

No unexplained packet, coordinate, separator, WIRE, or finalizer differences
remain. A focused regression proves this assertion from the authoritative
donor rather than an inferred schema.

## Local Proteus gate

A disposable copy visibly cold-opened and cold-reopened in Proteus 8
Professional after the delayed stability period. Neither open displayed a
Bad Object Record or other modal error, so neither was Ctrl+S-saved. The copy
SHA-256 remained byte-identical to the generated candidate. Screenshots are
stored beside the candidate under `local_proteus_gate/`. User visual acceptance
remains the final layout authority.
