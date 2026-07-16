# Totalmix full audit — 2026-07-15

## Evidence examined

- User-accepted mixed donor:
  `experiments/mixed_current_accepted_1x_v2_temp_2026_07_15/totalmix.pdsprj`
- Fresh bare 49-family control:
  `experiments/mixed_all_supported_totalmix_v1_temp_2026_07_15/cumulative_ladder_v1/S00_totalmix_fresh/S00_TOTALMIX_49F_1X_NO_TERMINAL.pdsprj`
- Fresh terminalized diagnostic (newly generated DSN, with `ROOT.CDB` copied
  only from the fresh bare control):
  `.../GENERATED_ALL49_TERMINALIZED_WITH_BARE_CONTROL_CDB_DIAGNOSTIC.pdsprj`

The diagnostic is not an edited copy of the accepted donor.  Its DSN was
emitted by the shared component placer plus shared terminal placer.

## Verified facts

1. All three projects contain the same 49 selected component families.  The
   generated terminal stream has 318 `$TERBIDIR` and 318 `WIRE` records, so
   the component bodies were not omitted from the DSN.
2. The bare 49-family control is not yet a compact visual mix.  Its body
   coordinates span an effectively single, extremely tall column (from
   `-5,100,320` to `372,364,000` in the audited packets).  The terminal stage
   preserves 47 of 49 direct body coordinate fields, so it is not the cause
   of that placement spread.  Bare layout must pass before a terminalized rung
   can be used as visual evidence.
3. The accepted donor and generated stream agree on the initial R/C attachment
   unit: `C1`, `R001A`, `R001B`, `00`, R1 + two WIREs, C0, C1 + two WIREs.
   R/C is therefore not the first structural divergence.
4. The former full-mix rebasing check was too weak.  It proved only that a
   matching active suffix existed somewhere before a WIRE.  It did not prove
   that the patched suffix was within the intended component packet.  In the
   audited candidate, active links for `Q41/NMOSFET` and `Q84/2N4401` landed
   outside their component packet ranges; U9 and U49 attachment units were
   also deferred tens of kilobytes from their associated packet.
5. Finalizer, suffix arithmetic, orientation counts, and terminal/WIRE counts
   are not sufficient acceptance evidence.  The generated candidate also
   has eight additional zero-length WIREs compared with the accepted donor.

## Required repair and gate

The shared placer must carry an owning component-packet locator for each
catalogue pin link through final address rebasing.  Rebased component suffix
positions must be resolved only inside that exact emitted packet, then checked
to be inside its packet boundary.  A global "last matching suffix before WIRE"
search is rejected.

Do not regenerate the 49-family pack until the following cumulative gate passes
with the locked mega donor:

1. compact bare two-family rung opens and both bodies fit the sheet;
2. the matching terminalized rung opens and each component-link suffix is in
   its own packet with a nonzero grid-contact short WIRE;
3. add two families only after the preceding rung passes.

If a rung exposes a byte grammar that no accepted donor proves, request the
smallest donor that isolates that grammar rather than guessing or copying an
accepted project at runtime.

## Gate-family follow-up

The fresh all-family runner initially omitted the existing
`force_grid_contact_short_wires` mode.  That was the common visual defect for
the DIL gate packages, not a `ROOT.CDB` difference:

| Family | Zero-length WIREs before grid mode | After grid mode |
| --- | ---: | ---: |
| 74HC00 | 12 | 0 |
| 74HC02 | 12 | 0 |
| 74HC04 | 0 | 0 |
| 74HC08 | 12 | 0 |
| 74HC32 | 12 | 0 |
| 74HC86 | 4 | 0 |
| 74HC266 | 4 | 0 |

With grid mode enabled, the fresh 49-family project reports 318 terminals,
318 WIREs, zero zero-length WIREs, and zero off-grid terminal contacts.  The
combined all-family route must therefore force this shared mode by default so
a future runner cannot silently emit the rejected zero-wire form.  Frozen
standalone family routes remain unchanged.
