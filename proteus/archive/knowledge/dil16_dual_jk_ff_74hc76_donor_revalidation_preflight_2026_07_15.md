# 74HC76 donor revalidation preflight — 2026-07-15

Authoritative donor:
`proteus_ic/donors/terminalized_catalogue_evidence/dil16_dual_jk_ff/74HC76/74HC76_terminalized_primary.pdsprj`.
The only placement source for the regenerated controls is the locked
`proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`.

## Complete donor audit

The donor archive contains `SCRIPTS/PWRRAILS.DAT` (17 bytes), `ROOT.CDB`
(384 bytes), `ROOT.DSN` (69,123 bytes), and `PROJECT.XML` (249 bytes).
`ROOT.CDB` has two pin rows (`U1:A`, `U1:B`) and one package property row
(`U1`). It identifies the package as `74HC76`, with the expected `74XX76.MDF`
model and DIL16 package properties.

The `ROOT.DSN` object stream begins at absolute byte `65184`; its object chunk
is 3,042 bytes and has fourteen `$TERBIDIR` records, fourteen WIRE records,
the two physical subparts, and one final `FF`. The complete stream topology is
asymmetric and must remain unchanged:

`12 terminals → U1:A → 7 A WIREs → 2 terminals → U1:B → 7 B WIREs → FF`.

The donor terminal order is:

`Q15, NQ14, Q11, NQ10, J4, CLK1, K16, J9, CLK6, K12, R3, S2, S7, R8`.

The A WIRE order is `J4, Q15, CLK1, K16, NQ14, S2, R3`; the B WIRE order is
`J9, Q11, CLK6, K12, NQ10, S7, R8`. Every terminal label, side/orientation,
subpart-relative pin coordinate, component-end link field, record separator,
and finalizer is already recorded in the 74HC76 catalogue profile. The active
link suffix is the low 16 bits of the absolute byte immediately before each
WIRE marker.

All fourteen donor WIREs are two-point, zero-length records because the donor
terminal contact equals the native pin endpoint. This proves the mandatory
active attachment-unit grammar, not a final terminal geometry. The donor
itself has left terminals at `1800` and right terminals at `0`.

## Current emitter comparison and bounded plan

A fresh locked-mega 1× placement resolves to `U41:A/B` and preserves the
donor’s two-subpart packet form. The old final profile transformed the donor's
explicit contact coordinates, which become the grid-aligned current pin
coordinates after beautification. It therefore emitted fourteen zero-length
final WIREs even though the report otherwise looked valid.

The repair is limited to the `74HC76` catalogue profile:

1. Mark staged native/grid diagnostics as requiring the donor-proven active
   terminal/component-link/WIRE unit.
2. Use `computed_outward_grid` with one 254000-unit outward step for grid and
   final contacts.
3. Keep `computed_terminal_contact_to_pin`, the existing two-subpart packet
   order, all link offsets, CDB policy, anchors, labels, and final `FF`.

This should leave native contact as a zero-length loader diagnostic only while
making grid/final routes nonzero grid-contact-to-exact-pin WIREs. The mandatory
gate sequence is native 1×, grid 1×, complete 1×, then complete 9× and 15×;
each must normal-open and cold-reopen in local Proteus before handoff.

## Loader-gated results

The bounded profile correction passed every planned local Proteus gate on
2026-07-15. Each disposable copy normal-opened and cold-reopened after the
required stability delay without `Bad Object Record`, `Fatal Error`, `LXLCORE`,
or library dialogs, and its hash remained unchanged.

- `C02_74HC76_NATIVE_PIN_CONTACT_sa.pdsprj` — active native diagnostic, 14
  donor-proven zero-length attachment units.
- `C03_74HC76_GRID_CONTACT_sa.pdsprj` — active grid diagnostic, 14 nonzero
  grid-contact-to-pin WIREs.
- `C04_74HC76_CATALOGUE_TERMINAL_sa.pdsprj` — complete 1× route, 14 nonzero
  WIREs.
- `S09_74HC76_9X_COMPLETE.pdsprj` — complete route, 126 nonzero WIREs.
- `S15_74HC76_15X_COMPLETE.pdsprj` — complete route, 210 nonzero WIREs.

The large-output capture shows repeated 74HC76 A/B sections with terminals
beside their pin contacts. The native zero-length unit remains diagnostic-only;
the grid/final outputs are the only terminal handoff candidates.
