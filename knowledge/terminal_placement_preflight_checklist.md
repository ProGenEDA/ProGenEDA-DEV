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
