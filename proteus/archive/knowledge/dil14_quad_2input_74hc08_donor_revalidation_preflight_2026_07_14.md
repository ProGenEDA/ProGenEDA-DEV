# 74HC08 authoritative donor preflight — 2026-07-14

## Scope

This is an additive `74HC08` profile promotion; no accepted two-pin, HC00, or
HC02 fact is changed. Pre-edit shared placer backup:
`backups/component_terminal_placer/component_terminal_placer_before_hc08_catalogue_20260714_060858.py`
(SHA-256 `ab995cff5230690110c39c198fbfe5fc01e49b58bd69096d55b9aa28dbad3bea`).

## Accepted donor inspected

`proteus_ic/donors/terminalized_catalogue_evidence/dil14_quad_2input_logic/74HC08/74HC08_user_terminalized_july04.pdsprj`
contains `PROJECT.XML`, `ROOT.DSN`, `ROOT.CDB`, and `SCRIPTS/PWRRAILS.DAT`.
`ROOT.CDB` has rows `U66:A`–`U66:D` plus property row `U66` (`74AND2.MDF`,
`DIL14`, `TTLHC`). It remains a normal placed-component CDB route.

The accepted 3,426-byte DSN object chunk has four component records, then
twelve terminal/WIRE attachment units. Component anchors are
`A=(-6,329,680,-2,265,680)`, `B=(-6,329,680,-4,043,680)`,
`C=(-2,519,680,-2,265,680)`, `D=(-2,519,680,-4,043,680)`. Current catalogue
subpart deltas and all link slots/`01 00` trailers match the donor. The final
coordinate ends in `FF`; the stream's separately verified structural finalizer
is one `FF`, not a guessed double finalizer.

## Attachment contract

Exact donor order: `8,11,3,6,1,2,4,5,9,10,12,13`; labels respectively
`Pin8O3`, `Pin11O4`, `Pin3O1`, `Pin6O2`, `Pin1I1`, `Pin2I2`, `Pin4I3`,
`Pin5I4`, `Pin9I5`, `Pin10I6`, `Pin12I7`, and `Pin13I8`. The first four are
0-degree outputs and the remaining eight are 1800-degree inputs. Every donor
contact is on the 254,000-unit grid and each is connected by a nonzero,
two-point WIRE to its exact pin. Current profile coordinates, labels, full WIRE
paths, endpoints, link slots, and order were all checked directly against this
donor with no geometry discrepancy.

The generated packet must preserve four placed subparts and append these units
after the component stream. Only current references, current coordinates, and
final address-rebased active suffixes are expected to differ from the donor.
The locked mega provides fifteen complete HC08 packages, so 1x, 9x, and 15x
are required loader gates.
