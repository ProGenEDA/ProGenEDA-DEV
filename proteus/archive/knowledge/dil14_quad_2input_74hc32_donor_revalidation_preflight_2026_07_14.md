# 74HC32 authoritative donor preflight — 2026-07-14

## Scope and freeze

This is an additive `74HC32` catalogue promotion. It does not alter the shared
terminal placer or any accepted two-pin, HC00, HC02, or HC08 route. The
pre-edit shared-placer snapshot is
`backups/component_terminal_placer/component_terminal_placer_before_hc32_catalogue_20260714_0628.py`
(SHA-256 `ab995cff5230690110c39c198fbfe5fc01e49b58bd69096d55b9aa28dbad3bea`).

## Entire accepted donor inspected

Authoritative donor:
`proteus_ic/donors/terminalized_catalogue_evidence/dil14_quad_2input_logic/74HC32/74HC32_user_terminalized_july04.pdsprj`.
It contains exactly `PROJECT.XML`, `ROOT.DSN`, `ROOT.CDB`, and
`SCRIPTS/PWRRAILS.DAT`. `ROOT.CDB` has four pin rows `U69:A` through `U69:D`
and one `U69` property row (`74HC32`, `DIL14`, `TTLHC`), establishing a normal
four-subpart placed-package route.

The 110,551-byte `ROOT.DSN` has a 3,422-byte object chunk. Its grammar is four
component records followed by twelve immediately adjacent terminal/WIRE units,
then the donor's terminal-coordinate `FF` and one structural final `FF`.
Current subpart anchors are
`A=(-995680,-2265680)`, `B=(-995680,-3789680)`,
`C=(-6329680,-2265680)`, and `D=(-6329680,-3789680)`.
All catalogue pin positions are component-relative; no current placement uses
the donor's absolute sheet position.

## Attachment and link contract

The exact unit order is `8,11,3,6,1,2,4,5,9,10,12,13` with labels
`Pin8O3`, `Pin11O4`, `Pin3O1`, `Pin6O2`, `Pin1I1`, `Pin2I2`, `Pin4I3`,
`Pin5I4`, `Pin9I5`, `Pin10I6`, `Pin12I7`, and `Pin13I8`. Pins 8/11/3/6 use
0 degrees; the remaining input pins use 1800 degrees. Every terminal contact
is on the 254,000-unit grid and every WIRE is a nonzero two-point donor path
from that contact to the exact pin. Donor WIRE marker offsets are
`1664,1822,1979,2136,2293,2450,2607,2764,2921,3079,3237,3395`.

All twelve current catalogue labels, angles, terminal contacts, full WIRE
coordinates, WIRE marker offsets, pin-link offsets, and `01 00` link trailers
were compared directly with this donor. There are no geometry discrepancies.
The older cache lacked only the authoritative-donor metadata, terminal/WIRE
order declaration, and guarded progressive capacity; those facts are added to
the same unified catalogue profile.

## Emission and gate plan

The shared catalogue route must retain the component stream, emit the twelve
units after it in the stated order, grid-snap each terminal contact, retain
the two-point exact-pin WIREs, and allocate terminal/component pin-link
suffixes from final WIRE addresses. The selected CDB is normalized only to the
placed packages by the existing shared stage. The locked mega exposes fifteen
complete HC32 packages, so staged 1x, then 9x and 15x, are required before
any mixed output.
