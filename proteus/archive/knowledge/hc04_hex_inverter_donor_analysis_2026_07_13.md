# 74HC04 hex-inverter donor preflight — 2026-07-13

## Authoritative active terminal source

The active single-package evidence is the user-provided project:

`proteus_ic/donors/terminalized_catalogue_evidence/dil14_hex_inverter/74HC04/E04_74HC04_1X_NO_TERMINAL_CONTROL.pdsprj`

Its filename is historical: the actual ROOT.DSN object stream contains twelve
active `$TERBIDIR` records and twelve `WIRE` records. A disposable copy opened
normally in local Proteus after 20 seconds. Its members are exactly:

| Member | Size |
| --- | ---: |
| `SCRIPTS/PWRRAILS.DAT` | 17 |
| `ROOT.CDB` | 498 |
| `ROOT.DSN` | 111,435 |
| `PROJECT.XML` | 249 |

`ROOT.DSN` has a 4,306-byte object stream ending in `FF FF`; `ROOT.CDB` SHA256
is `a54c47669fc20cb5bc1163f52f7b5e73a4a346de5feec938fdb50df840a85bd7`.
The CDB is evidence only: generated projects continue to use the component
placer's selected-package CDB subset.

The nearby `new_component_mega_supported_terminalized_evidence` HC04 project
is an integration circuit (19 terminals and 43 WIREs), so it is not a suitable
solo attachment grammar source. The older `T02_74HC04_ALL6_NOT` project has
six ordinary terminal/WIRE pairs but no `$TERBIDIR` records; it remains
coordinate background only, not the active-link authority.

## Donor object-stream facts

The E04 component packet has `U61:A` through `U61:F`; each logical inverter
has one left input and one right output.

| Subpart | Input pin | Output pin | Input link slot | Output link slot |
| --- | ---: | ---: | ---: | ---: |
| A | 1 | 2 | subpart end -9 | subpart end -5 |
| B | 3 | 4 | subpart end -9 | subpart end -5 |
| C | 5 | 6 | subpart end -9 | subpart end -5 |
| D | 9 | 8 | subpart end -9 | subpart end -5 |
| E | 11 | 10 | subpart end -9 | subpart end -5 |
| F | 13 | 12 | subpart end -9 | subpart end -5 |

The donor's active component-link fields use trailer `01 00`. Terminal labels
are `INpin1`, `OUTpin2`, `INpin3`, `OUTpin4`, `INpin5`, `OUTpin6`, `OUTpin8`,
`INpin9`, `OUTpin10`, `INpin11`, `OUTpin12`, and `INpin13`; left terminals
are 1800 and right terminals are 0. Every donor WIRE reaches its corresponding
exact pin endpoint.

## Current locked-mega comparison

The locked component placer emits a 1x packet as `U202:A` through `U202:F`
with a four-character package reference. Its bare group is 2,280 bytes (object
stream positions 2–2,281), versus the E04 packet's three-character `U61`
references. The original HC04 catalogue stored whole-package link offsets from
the old packet. In the current candidate this places pin-2's link field at
position 381 while the current `U202:B` marker starts at 382, overwriting that
marker and leaving Proteus on its loading splash. The no-terminal control
opens normally, so the component placer packet itself is not the fault.

This is the same reference-width defect already proven for the DIL14 quad-gate
group. It must be repaired additively in the catalogue with the six
donor-derived subpart end offsets above. No terminal packet, wire construction,
or accepted family route is to be changed. The final `:F` slot is resolved
against the end of the current component packet, yielding the same -9/-5
relative fields.

## Required regression

Before handoff, regenerate a shared-placer 1x HC04 candidate and verify:

1. all 12 final component-link fields fall within their own current
   `U202:A`–`:F` records;
2. twelve active terminals and twelve short WIREs persist after final-address
   rebasing;
3. every terminal contact is grid-aligned and every WIRE is local to its pin;
4. a copied output opens in Proteus, then save/cold-reopen succeeds; and
5. the accepted DIL14 quad-gate regression matrix remains unchanged.

## Complete attachment grammar recovered from E04

The initial repaired probe still used the old HC04 two-point WIRE background.
That was not the active donor grammar: E04 places the component stream first,
then twelve terminal/WIRE units, each terminal immediately followed by its own
routed WIRE.  Their order is:

`2, 10, 6, 4, 8, 12, 1, 11, 5, 3, 9, 13`.

The six output WIREs each have three points and the input WIREs have three or
four points.  The current shared planner already serializes arbitrary
donor-derived polyline WIREs; its new additive
`donor_attachment_unit_order` catalogue field only preserves the authoritative
unit order for clean-packet families.  Families without that field retain their
existing output order unchanged.

E04 uses subpart anchors A--F at, respectively:

| Subpart | Anchor relative to F |
| --- | ---: |
| A | (-5,080,000, 1,524,000) |
| B | (0, 1,524,000) |
| C | (-4,826,000, -2,032,000) |
| D | (254,000, -2,032,000) |
| E | (-5,080,000, 0) |
| F | (0, 0) |

Each pin's exact endpoint, grid contact, label, orientation, active link slot,
and full 3-/4-point WIRE path is now recorded in the HC04 catalogue profile.
The shared planner rebases those local donor paths to the current component
placer's per-subpart anchors, then retargets only the two endpoints to the
current grid contact and exact pin.  No accepted two-pin or quad-gate geometry
is changed.

The first disposable full-grammar 1x output had twelve terminals, twelve WIREs,
grid-valid contacts, correct final-address link rebasing, and a normal
responsive Proteus schematic window at the shortened 12-second loader check.
It still requires the documented cold-reopen and regression gate before
promotion.
