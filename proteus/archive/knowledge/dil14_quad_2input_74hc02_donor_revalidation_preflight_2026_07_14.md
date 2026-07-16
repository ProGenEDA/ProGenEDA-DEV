# 74HC02 authoritative donor preflight — 2026-07-14

## Scope

This is an additive `74HC02` profile repair. Frozen two-pin behavior, the
accepted HC00 route, and all other profiles remain untouched. The pre-edit
shared-placer backup is
`backups/component_terminal_placer/component_terminal_placer_before_hc02_catalogue_20260714_055530.py`
(SHA-256 `ab995cff5230690110c39c198fbfe5fc01e49b58bd69096d55b9aa28dbad3bea`).

## Full accepted donor facts

Authoritative project:
`proteus_ic/donors/terminalized_catalogue_evidence/dil14_quad_2input_logic/74HC02/74HC02_user_terminalized_july04.pdsprj`.
It contains `PROJECT.XML`, `ROOT.DSN` (112,624 bytes), `ROOT.CDB`, and
`SCRIPTS/PWRRAILS.DAT`. `ROOT.CDB` has native pin rows `U58:A`–`U58:D` and one
`U58` property row (`74NOR2.MDF`, `DIL14`, `TTLHC`); no CDB alteration is
needed for terminal attachment.

The 3,442-byte DSN object stream begins `00 00`, has four `74HC02` component
records first, then 12 terminal/WIRE units, and has one final `FF`. Anchors are
`A=(-5,567,680,-4,297,680)`, `B=(-5,567,680,-6,837,680)`,
`C=(-2,011,680,-4,297,680)`, and `D=(-2,011,680,-6,837,680)`. All pin-link
fields use `01 00` after the active suffix. Existing subpart-relative link
slots in the catalogue match all twelve actual donor fields.

## Exact attachment route

The donor order is `10, 13, 4, 1, 2, 3, 5, 6, 8, 9, 11, 12` with labels
`Pin10O3`, `Pin13O4`, `Pin4O2`, `Pin1O1`, `Pin2I1`, `Pin3I2`, `Pin5I3`,
`Pin6I4`, `Pin8I5`, `Pin9I6`, `Pin11I7`, and `Pin12I8`. Outputs use 0
degrees and inputs 1800. Every contact is on the 254,000-unit grid and every
WIRE is nonzero. Pins 5 and 6 use three-point input polylines; the partial
catalogue had retained only two points and incorrectly identified the middle
vertex as terminal contact. The repair preserves all points and uses the final
donor endpoint as the terminal contact.

The current pinned coordinate model is donor-relative to the current subpart
anchor. It therefore remains independent of the mega donor's source positions
after component placement/beautification. Expected output changes from the
donor are reference names, current component coordinates, and final absolute
WIRE-link suffixes only. Required invariants are four complete subparts, 12
terminals, 12 adjacent terminal/WIRE units in this order, matching active link
suffixes, `01 00` trailers, and single-FF finalization.

## Scale condition

The locked mega has twelve complete safe HC02 packages. The 9x (108 units) and
12x (144 units) complete paths passed normal/cold-reopen gates. A fresh 15x
component-placer control stops before terminal emission with only twelve
complete packages, so this is a measured source availability boundary rather
than a terminal-placement limitation.
