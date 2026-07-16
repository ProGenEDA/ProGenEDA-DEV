# 74HC86 authoritative donor preflight — 2026-07-14

## Scope and freeze

This is an additive `74HC86` catalogue repair. It does not change the shared
terminal placer or accepted two-pin, HC00, HC02, HC08, or HC32 behavior. The
pre-edit shared-placer snapshot is
`backups/component_terminal_placer/component_terminal_placer_before_hc86_catalogue_20260714_0648.py`
(SHA-256 `ab995cff5230690110c39c198fbfe5fc01e49b58bd69096d55b9aa28dbad3bea`).

## Entire accepted donor inspected

Authoritative donor:
`proteus_ic/donors/terminalized_catalogue_evidence/dil14_quad_2input_logic/74HC86/74HC86_user_terminalized_july04.pdsprj`.
It contains exactly `PROJECT.XML`, `ROOT.DSN`, `ROOT.CDB`, and
`SCRIPTS/PWRRAILS.DAT`. `ROOT.CDB` has `U73:A` through `U73:D` plus property
row `U73`, proving a normal four-subpart `DIL14` TTL package route.

The 110,611-byte `ROOT.DSN` has a 3,482-byte object chunk: four component
records first, 12 immediate terminal/WIRE units, then the donor coordinate
`FF` and one structural final `FF`. Current anchors are
`A=(-6202680,-3789680)`, `B=(-6202680,-2011680)`,
`C=(-2138680,-2011680)`, and `D=(-2138680,-3789680)`. The profile stores
relative geometry from those current anchors; it does not reuse donor sheet
coordinates at runtime.

## Attachment and complete delta audit

Exact donor order is `6,3,8,11,4,5,1,2,9,10,12,13` with labels
`Pin6O2`, `Pin3O1`, `Pin8O3`, `Pin11O4`, `Pin4I3`, `Pin5I4`, `Pin1I1`,
`Pin2I2`, `Pin9I5`, `Pin10I6`, `Pin12I7`, and `Pin13I8`. The four outputs
use 0 degrees and the eight inputs use 1800 degrees. Every contact is on the
254,000-unit grid and every attachment ends at the exact component pin.

The authoritative WIRE point counts are `3,3,2,3,3,2,2,2,3,3,3,2` at marker
offsets `1668,1833,1998,2156,2321,2486,2643,2800,2957,3123,3289,3455`.
The older profile had seven truncated paths: pins 6, 3, 11, 4, 9, 10, and 12
were missing their final terminal-contact point. All other labels, angles,
contacts, link offsets, `01 00` trailers, marker offsets, and relative pin
facts already matched the accepted donor. The repair restores only those full
paths and adds authoritative provenance/order/capacity metadata.

## Emission and gate plan

The unified shared placer must retain the four component packets, append the
twelve units in the donor order, grid-snap terminal contacts, keep the full
two/three-point donor polylines, and rebase all active terminal/component links
from final WIRE addresses. Its selected CDB normalization remains the existing
shared behavior. The locked mega exposes fifteen complete packages: prove
native-contact, grid-contact, and complete 1x first, then 9x/15x before any
mixed circuit.
