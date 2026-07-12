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
- Terminal contact must land on the Proteus grid.
- Left pins use `1800`; right pins use `0`.
- Each terminal has a nonzero, donor-proven short WIRE to the exact pin.
- Terminal suffix and component pin-link suffix must be allocated from the final WIRE address.
- Encode only the new family/profile exception; do not replace accepted generic logic.

## 4. Verify before a handoff

- Compile and run focused tests for the new family.
- Run the full regression set for every accepted family touched by shared code.
- Regenerate 1× first; compare it byte-for-byte or by fully enumerated structural deltas against the donor.
- Test 9×/15×/23× only after the 1× route is accepted.
- Use a 24-second local loader wait for iterative checks; reject every modal error.
- On a copied output: cold open, Ctrl+S, inspect structural mutation, cold reopen, and record the result.
- Only then ask the user for visual/layout acceptance.

## Current freeze note — 2026-07-12

The shared generic two-pin route (diodes, zeners, 40EPS08, LED-RED, FUSE and SWITCH) is user-accepted and frozen. An attempted geometry rewrite made during mixed BJT research was reverted. Do not change it without a user-supplied failure and an accepted donor for that exact route.
