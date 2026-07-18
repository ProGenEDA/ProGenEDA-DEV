# Catalogue-only gate totalmix probe — 2026-07-17

## Scope and freeze

This is an additive diagnostic for the seven locked-mega gate families
`74HC00`, `74HC02`, `74HC04`, `74HC08`, `74HC32`, `74HC86`, and `74HC266`.
It does not change any accepted native two-pin route, standalone catalogue
geometry, terminal orientation, short-WIRE coordinates, active-link encoding,
or component packet.

The shared placer backup made before the diagnostic is:

`proteus/archive/backups/component_terminal_placer/component_terminal_placer_20260717_195914_before_catalogue_only_totalmix_gate_probe.py`

## Authoritative evidence already audited

The route reuses the existing `totalmix_combined_v1` catalogue profile derived
from the user-saved `terminalized49.pdsprj`. Its complete DSN audit and the
accepted component-local gate attachment grammar are already recorded in
`totalmix_combined_donor_audit_2026_07_15.md`. No donor packet, coordinate, or
ROOT.CDB content is copied at runtime.

## Failure isolated before the change

- Every gate family generates statically through the current component placer
  and shared catalogue terminalizer.
- `74HC08` 10x cold-opened and cold-reopened without a dialog; screenshots show
  the gate units with terminals and nonzero short wires.
- The homogeneous catalogue serializer loads a seven-family 1x project without
  a dialog but renders only a subset of families. At 3x it raises a corrupt
  device-library-name dialog and at 5x it raises `VGDVC.DLL [000190DA]`.
- Tightening placement to a 35,000,000-unit shelf made all seven component
  bounding boxes fit within the sheet but did not restore the missing rendered
  families. This disproves coordinates as the root cause of the disappearing
  gate packets.

## Diagnostic change

Permit `totalmix_combined_v1` to run with catalogue families and zero native
families. The existing conservative mixed route continues to require at least
one native and one catalogue family. The test is accepted only if a freshly
placed seven-family project visibly renders every family, has grid-aligned
terminal contacts and nonzero short wires, and passes screenshot-backed cold
open and cold reopen.

## Result: rejected and reverted

The diagnostic project cold-opened and cold-reopened without a modal error,
but the screenshots rendered only the `74HC08` package. Static counts of seven
components, 84 terminals, and 84 WIREs were therefore false-positive evidence
for visual completeness. The zero-native guard relaxation was reverted. The
accepted shared placer remains unchanged; future mixed gate work must recover
the old accepted gate package-boundary insertion behavior rather than forcing
the combined native/catalogue serializer into an unproven mode.

## Promoted executable boundary

The modern application route was promoted only for one gate family per
project. It uses the current component placer output as its base, the shared
catalogue terminalizer, and optional `terminal_label_projection`; it does not
use E001. Screenshot-backed cold-open/cold-reopen ceilings are `74HC00=8`,
`74HC02=4`, and `74HC04/08/32/86/266=10`. The 74HC02 8x, 9x, and 10x trials
all raise `VGDVC.DLL [000190DA]`; 1x and 4x open normally. The executable
rejects requests above these tested ceilings and rejects every mixed-gate or
gate-plus-other-family request rather than returning a statically valid but
visually incomplete file.
