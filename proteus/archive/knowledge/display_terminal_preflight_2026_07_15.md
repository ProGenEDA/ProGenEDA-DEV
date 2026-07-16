# Seven-segment terminal preflight — 2026-07-15

## Scope and frozen routes

This is an additive repair limited to the two display profiles:

- `7SEG-COM-AN-BLUE` (the Proteus body marker is `7SEG-COM-ANODE`)
- `7SEG-COM-CAT-BLUE`

It must not alter any frozen two-pin, transistor, control-symbol, or logic-IC
route.  The shared placer was backed up before implementation as
`backups/component_terminal_placer/component_terminal_placer_pre_display_repair_2026_07_15.py`.

## Authoritative accepted donors inspected in full

| Family | Accepted donor | Archive members | `ROOT.DSN` / `ROOT.CDB` bytes |
| --- | --- | --- | --- |
| Common anode | `proteus_ic/donors/terminalized_catalogue_evidence/display_7seg/7SEG-COM-AN-BLUE/7SEG-COM-AN-BLUE_user_terminalized_july04.pdsprj` | `SCRIPTS/PWRRAILS.DAT`, `ROOT.CDB`, `ROOT.DSN`, `PROJECT.XML` | 109,163 / 322 |
| Common cathode | `proteus_ic/donors/terminalized_catalogue_evidence/display_7seg/7SEG-COM-CAT-BLUE/7SEG-COM-CAT-BLUE_user_terminalized_july04.pdsprj` | `SCRIPTS/PWRRAILS.DAT`, `ROOT.CDB`, `ROOT.DSN`, `PROJECT.XML` | 109,549 / 381 |

The complete object streams, all terminal records, every WIRE, component link
slots, `ROOT.CDB`, stream prefix/separators, and final tails were inspected.
The user-accepted projects both use a `00 00` object prefix, immutable D20
packet first, display packet(s), then eight trailing active terminal/WIRE
units.  Their final object streams end in `ff ff`.

### Common-anode donor grammar

- Component body marker: `7SEG-COM-ANODE`; this is why a profile named
  `7SEG-COM-AN-BLUE` has no strict same-name marker anchor and deliberately
  uses its donor-relative component-body bbox fallback.
- Bare placed 1x control is D20 (375 bytes) + one finalized anode packet
  (399 bytes), for a 776-byte object chunk including prefix/finalizer.
- Donor packet ends at object offset 776.  Its final `ff` is consumed before
  the first terminal unit, then the eight `terminal, WIRE` pairs are appended
  in this order: `CommonAnode`, `a`, `b`, `c`, `g`, `d`, `e`, `f`.
- The component pin-link fields are at end-relative offsets
  `-5, -33, -29, -25, -9, -21, -17, -13`, respectively.  Every trailer is
  `0100`.
- `CommonAnode` is right-facing (`0`); `a` through `g` are left-facing
  (`1800`).  All terminal contacts are grid aligned; wires preserve the donor
  2- or 3-point topology and end at the exact off-grid component pin.

### Common-cathode donor grammar

- Bare cathode control needs D20 (375 bytes), a non-final cathode packet
  (403 bytes), and a finalized anode sentinel (399 bytes).  The sentinel is
  hidden infrastructure, is not a user component, and receives no terminals.
- The accepted cathode donor confirms that the sentinel is required to retain
  the complete display packet boundary.  The previous component placer
  incorrectly omitted it because no raw mega anode row ends in `ff`; raw rows
  are finalized by the existing `_display_row_as_final` rule.
- The eight trailing pairs are ordered `commoncath`, `a`, `b`, `c`, `d`, `e`,
  `f`, `g`.  `commoncath` uses a four-point donor dogleg; all segment wires
  are short one-segment lines.  Right/left terminal angles are `0` / `1800`.
- Pin-link offsets from the cathode packet end are `-3, -31, -27, -23, -19,
  -15, -11, -7`; every trailer is `0100`.  The active suffix is the low 16
  bits of `(absolute ROOT.DSN WIRE marker - 24)` and must be rebased only after
  the final stream is serialized.

## Locked-mega control evidence

The only placement donor is
`proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`.
It contains 100 raw cathode and 100 raw anode rows.  Neither raw anode row
ends in `ff`; the accepted placer finalizes the selected row with `00 ff`.
The fresh no-terminal controls are:

- `S12_7SEG_COM_AN_BLUE_1X_NO_TERMINAL.pdsprj`: D20 + final anode row;
  opens normally.
- `S13_7SEG_COM_CAT_BLUE_1X_NO_TERMINAL.pdsprj`: D20 + finalized cathode
  row; opens normally, but lacks the donor-required anode sentinel.

The full mega `ROOT.CDB` is intentionally preserved for display output.  It
already opens for the component-placer controls and does not have a stable
synthetic package key for `DISPLAY_CC_001` / `DISPLAY_ANODE_SENTINEL`.
Rebuilding it from those generated labels would be a separate, unproven CDB
mutation; this display terminal repair is DSN-only.

## Complete explained delta set before implementation

1. The anode generic trailing-attachment guard incorrectly requires every
   component record to start with `ff`.  Display packets legitimately start
   with `00 08 ff`; their byte-contiguous D20/display stream is otherwise
   complete and donor-proven.
2. The cathode early `raise` disables its already catalogue-driven path.
3. Cathode-only placement omitted the required final anode sentinel because
   it looked only for an already-final raw row.  Existing raw-row finalization
   is the evidence-backed fix, not a new donor or a D20 mutation.
4. The generic display path would otherwise normalize `ROOT.CDB` using
   synthetic display keys.  The accepted control proves preserving the locked
   mega CDB is the conservative route.
5. The accepted anode donor's body anchor is off-grid by 20,320 units, while
   the current component placer deliberately moves the bare body onto the
   Proteus grid.  Re-targeting its donor polyline to that grid body collapsed
   the seven segment WIREs to zero length.  The evidence-backed grid-body
   route therefore keeps the placed body unchanged, uses each catalogue
   pin's existing one-grid outward contact step, and emits the existing
   catalogue-leading short WIRE encoding directly from that grid contact to
   the current pin.  This is additive to `7SEG-COM-AN-BLUE` only; the cathode
   profile and every accepted family remain unchanged.
6. The anode's complete donor proves its `0100` active-link class and its
   `component_stream_then_attachment_units` order.  A fresh locked-mega
   `RESISTOR + CAP + 7SEG-COM-AN-BLUE` output proved that the display units can
   be emitted immediately after the display's own finalized packet in the
   shared totalmix route, with D20 byte-preserved.  It must therefore be a
   local component attachment in that route, rather than a synthetic tail
   zone or an imported donor packet.

No accepted-family geometry, terminal encoding, pin mapping, D20 bytes,
component placement coordinates, or two-pin behavior will be changed.

## Required 1x gate sequence

For each display, generate from the locked mega through the shared placer only:

1. active units at native pin contacts;
2. active units at grid contacts;
3. labelled, grid-contact terminals plus donor-proven wires and final address
   rebasing.

Each stage must cold-open and be compared with the preceding stage and the
accepted donor.  Only then may it be included in the fast solo matrix.
