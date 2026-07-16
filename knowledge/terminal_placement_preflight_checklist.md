# Terminal Placement Preflight Checklist

Use this before changing `src/proteusgen/component_terminal_placer.py`.

## 1. Freeze the accepted route

- List every accepted family whose code/profile can be reached by the proposed change.
- Do not alter an accepted family to solve a new family or a new mixed combination.
- Copy the shared placer to `backups/component_terminal_placer/` before editing.
- Identify the new family/profile branch that will contain the additive change.

## 2. Analyse the entire authoritative donor first

For the user-provided accepted `.pdsprj`, inspect and write one compact note under `knowledge/` covering:

- every archive member and the complete `ROOT.DSN` object stream;
- component packets, reference/family markers, body anchors, pin-link offsets and trailers;
- every terminal record: label, suffix, angle, symbol coordinates and contact;
- every `WIRE`: full points, order, immediate neighbouring bytes, suffix/address relation and final tail;
- `ROOT.CDB` pin/property rows and any Ctrl+S mutation;
- object stream prefix, separators, packet tails, finalizer and record order;
- relative pin coordinates from the component anchor, never only absolute screen coordinates.

Do not start implementation while any donor-vs-generated structural difference remains unexplained.

## 3. Plan only from evidence

- Catalogue the family’s pins: number, name, role, side, relative coordinate, link field and donor source.
- The terminal attaching edge/contact, not merely the symbol origin, must land
  exactly on a vertical/horizontal Proteus grid intersection.
- Left pins use `1800`; right pins use `0`.
- Each terminal has a nonzero, donor-proven short WIRE to the exact pin.
- Terminal suffix and component pin-link suffix must be allocated from the final WIRE address.
- Encode only the new family/profile exception; do not replace accepted generic logic.
- For a terminal-stream repair, do not change `ROOT.CDB` unless the user
  explicitly reopens CDB work.

## 3a. Required staged 1x loader proof

Before creating a complete new-family 1x candidate, prove each additive stage
on a disposable output and compare its exact DSN delta to the accepted donor:

1. Emit the correctly oriented terminal at the native donor pin/contact
   (`1800` left, `0` right); cold-open it.
2. Move its attaching contact to the donor-derived grid intersection; cold-open
   it again. The component pin may remain off-grid.
3. Add the donor-proven terminal label, short WIRE to the exact pin, and final
   active terminal/component-link suffixes; cold-open and cold-reopen it.

If a stage fails, stop at that stage and byte-compare only the newly introduced
record fields with the donor. Do not jump directly to a complete speculative
terminal packet.

## 4. Verify before a handoff

- Compile and run focused tests for the new family.
- Run the full regression set for every accepted family touched by shared code.
- Regenerate 1× first; compare it byte-for-byte or by fully enumerated structural deltas against the donor.
- Test 9×/15×/23× only after the 1× route is accepted.
- Use the 12-second local loader wait only after the schematic window appears;
  reject every modal error.
- On a copied output: cold open, inspect structural mutation, cold reopen, and
  record the result. Do not Ctrl+S a normally opening project. If a `Bad Object
  Record` dialog is dismissed and the schematic opens correctly, Ctrl+S only
  that disposable copy, compare its delta, then cold-reopen it.
- Only then ask the user for visual/layout acceptance.

## Current freeze note — 2026-07-12

The shared generic two-pin route (diodes, zeners, 40EPS08, LED-RED, FUSE and SWITCH) is user-accepted and frozen. An attempted geometry rewrite made during mixed BJT research was reverted. Do not change it without a user-supplied failure and an accepted donor for that exact route.

## Completed preflight — 2026-07-15 `totalmix` DSN repair

- Authority: user-provided `experiments/mixed_current_accepted_1x_v2_temp_2026_07_15/totalmix.pdsprj`; the user explicitly limited this investigation to `ROOT.DSN`, so no `ROOT.CDB` comparison or mutation was used.
- Backup created before the repair: `backups/component_terminal_placer/component_terminal_placer_20260715_102311_before_totalmix_dsn_audit_repair.py`.
- Complete DSN inventory and donor-vs-candidate diff: `knowledge/totalmix_combined_donor_audit_2026_07_15.md` plus the machine-readable audit beside its experiment.
- Evidence-backed changes only: trim the eight proven inline `00` packet finalizers, split the two donor-proven attachment zones, and remove the rejected canonical component sort. Accepted two-pin/current routes remain unchanged.
- Gate: focused mixed/totalmix regression tests passed; compile/catalogue-JSON checks passed; freshly placed 49-family 1x candidate passed normal open and cold reopen without a modal error or save mutation.

## Completed preflight - 2026-07-15 BRIDGE 42-family additive route

- Authority: `proteus_ic/donors/terminalized_catalogue_evidence/four_pin_rectifier_transformer/BRIDGE/BRIDGE_user_terminalized_july04.pdsprj`; full member, DSN/CDB, component, pin-link, terminal, WIRE, relative-frame, separator, and finalizer inventory is recorded in `knowledge/totalmix_missing7_donor_preflight_2026_07_15.md`.
- Freeze: accepted two-pin/current/BJT/control/NE555/LM741/74HC74 behavior is unchanged. The sole additive facts are BRIDGE's `0200` link class, its independent tail zone, rank, and four donor unit order entries in the component catalogue.
- Backup: `backups/component_terminal_placer/component_terminal_placer_20260715_202651_before_missing7_totalmix_bridge_profile.py`.
- Evidence checks: `RIGHT, TOP, BOTTOM, LEFT` terminal/WIRE unit order; 0/0/0/1800 orientations; grid contact; nonzero wire to the exact pin; address-derived terminal/component link suffixes; and explicit `FF FF` object finalizer.
- Gate: focused BRIDGE and all totalmix/mixed regressions, JSON/compile checks, plus a fresh 42-family normal/cold Proteus open gate. The normally opening disposable copy was not saved.

## Completed preflight - 2026-07-15 TRAN-2P2S 43-family additive route

- Authority: `proteus_ic/donors/terminalized_catalogue_evidence/four_pin_rectifier_transformer/TRAN-2P2S/TRAN-2P2S_user_terminalized_july04.pdsprj`; full member, DSN/CDB, component, pin-link, terminal, WIRE, relative-frame, separator, and finalizer inventory is recorded in `knowledge/totalmix_missing7_donor_preflight_2026_07_15.md`.
- Freeze: BRIDGE and every previously accepted family remain unchanged. The additive profile facts are only TRAN-2P2S's active `0200` link class, four-pin tail-zone membership/rank, and donor unit order.
- Backup: `backups/component_terminal_placer/component_terminal_placer_20260715_203750_before_missing7_totalmix_tran_2p2s_profile.py`.
- Evidence checks: `TOPRIGHT, BOTTOMRIGHT, TOPLEFT, BOTTOMLEFT` terminal/WIRE order; `0,0,1800,1800` orientation; grid contact; nonzero wire to exact pin; final-address terminal/component suffixes; and `FF FF` termination. The donor's bent bottom-left wire is documented; the fresh collinear grid contact safely emits a direct segment.
- Gate: focused transformer and all totalmix/mixed regressions, JSON/compile checks, plus a fresh 43-family normal/cold Proteus open gate. The normally opening disposable copy was not saved.

## Completed preflight - 2026-07-15 7SEG-COM-AN-BLUE 44-family additive route

- Authority: `proteus_ic/donors/terminalized_catalogue_evidence/display_7seg/7SEG-COM-AN-BLUE/7SEG-COM-AN-BLUE_user_terminalized_july04.pdsprj`; full DSN/CDB, component, terminal, WIRE, pin-link, frame, separator, and finalizer audit is recorded in `knowledge/display_terminal_preflight_2026_07_15.md` and `knowledge/totalmix_missing7_donor_preflight_2026_07_15.md`.
- Freeze: all 43 accepted family routes remain byte- and geometry-unchanged. The additive facts are only the anode display's grid-body contact policy, direct grid-contact-to-current-pin WIRE policy, local attachment membership, and `0100` active-link trailer.
- Backup: shared placer behavior was not edited; the change is catalogue-only.
- Evidence checks: eight terminal/WIRE units, contacts on grid intersections, required left/right orientations, eight nonzero exact-pin wires, matching final-address `0100` terminal/component suffixes, local attachment immediately after the display packet, immutable D20 preservation, and explicit finalizer.
- Gate: focused anode/catalogue/totalmix regressions, compile check, a fresh solo anode normal/cold gate, a fresh RESISTOR+CAP+anode normal/cold mixed gate, and the actual cumulative 44-family normal/cold gate. No normally opening file was saved.

## Completed preflight - 2026-07-15 7SEG-COM-CAT-BLUE 45-family cumulative route

- Authority: `proteus_ic/donors/terminalized_catalogue_evidence/display_7seg/7SEG-COM-CAT-BLUE/7SEG-COM-CAT-BLUE_user_terminalized_july04.pdsprj`; its complete DSN/CDB, packet, terminal, WIRE, link, coordinate, order, and finalizer audit is in `knowledge/display_cathode_terminal_preflight_2026_07_15.md`.
- Cumulative invariant: the candidate starts with the committed 44-visible-family anode request and adds cathode as visible family 45; it does not recreate a 38-family base. `D20` remains display infrastructure only.
- Freeze: no accepted 44-family route is changed. The only shared-emitter extension handles the donor-proven common-cathode/common-anode adjacent packet boundary and is exercised by a focused two-visible-display regression.
- Evidence checks: the cathode's `commoncath` `-3` link offset is patched relative to the original 403-byte cathode row while the adjacent visible anode row is retained in the same emitted block; both display families have eight terminal/WIRE units, grid-aligned contacts, correct left/right angle, nonzero exact-pin wire paths, and final-address `0100` link suffixes.
- Gate: focused anode/cathode mixed regressions passed (`2 passed`), source compiled, and the newly placed real cumulative 45-family output normal-opened and cold-reopened with no modal error or hash mutation. No normally opening file was saved.

## Superseding combined-display audit - 2026-07-15

- Authority: user-provided
  `proteus_ic/donors/terminalized_catalogue_evidence/display_7seg/combined_45_family/both7segplaced_user_terminalized_45f_20260715.pdsprj`.
- The generated G08 45-family file is visually rejected. Its static report
  claimed local display attachment, but the final DSN instead batches both
  display terminal/WIRE blocks after both display packets.
- The authoritative combined donor proves local `AN component → AN units → CC
  component → CC units` ordering, exact display pin labels, and context-specific
  `0200` anode / `0300` cathode active link trailers.
- Treat the preceding combined-display completion as superseded for future
  emission. The isolated display donors remain valid only for their separately
  proven solo routes.
- See `knowledge/combined_7seg_45f_donor_audit_2026_07_15.md`. No source or
  catalogue change may be made until the repair preflight is completed from
  this donor.

## Completed preflight - 2026-07-16 frozen 43-family 3x full-WIRE-pointer route

- Authority: user-created, Proteus-saved
  `experiments/frozen_43_family_mix_matrix_v1_temp_2026_07_16/00_user_editable_compact_43f/U00_43F_ACCEPTED_TERMINALIZED_USER_MULTIPLY.pdsprj`.
  Its complete archive/DSN/CDB/packet/terminal/WIRE/link/finalizer audit is
  `knowledge/frozen_43_manual_3x_donor_audit_2026_07_16.md`.
- Scope: the frozen 43-family mix-scale route only. Accepted 1x legacy routes,
  including G02's 27 `0100` active link fields, are not changed.
- Evidence: U00 has 129 components and 639 terminal/WIRE pairs. Every active
  terminal and matching component pin link is the complete little-endian
  32-bit final WIRE address `(object_start + wire_marker - 24)`. U01 rebased
  only the low word and resolves 268/639 links; U00 resolves 639/639.
- Backup created before edit:
  `backups/component_terminal_placer/component_terminal_placer_20260716_140237_before_frozen_43_full_wire_pointer_rebase.py`.
- Implemented additive behavior: an explicit full-address final-link encoding
  disables low-word label jitter, patches all four bytes of the known terminal
  and component fields, and validates complete address uniqueness. It will not
  expand the legacy global trailer allow-list or replace existing serializers.
- The manual donor's three-copy closure order is explicitly non-causal: it is
  the user's copy/paste result, not a required component-stream ordering rule.
  The original placed-design order remains unchanged, including for uneven
  future family counts.
- Completed verification: the focused 43-family 3x regression generated the
  original-order 129-component stream and proved all 639 terminal and
  component fields equal their final 32-bit WIRE addresses; no label jitter
  occurred. Remaining verification is accepted-family regressions, compile
  checks, a fresh generated 3x static audit, and a delayed normal/cold Proteus
  gate.
