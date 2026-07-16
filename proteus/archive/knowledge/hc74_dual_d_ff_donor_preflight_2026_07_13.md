# 74HC74 dual D flip-flop donor preflight — 2026-07-13

## Authoritative source

The actual active terminal source is:

`proteus_ic/donors/terminalized_catalogue_evidence/dil14_dual_d_ff/74HC74/74HC74_terminalized_primary.pdsprj`

It is byte-identical to the mirrored supported-evidence file and to
`proteus_ic/donors/sequential_ics_batch3/74HC74.pdsprj`. Local Proteus 8.13
opened the source normally in the shortened 12-second loader check.

Members:

| Member | Size |
| --- | ---: |
| `SCRIPTS/PWRRAILS.DAT` | 17 |
| `ROOT.CDB` | 374 |
| `ROOT.DSN` | 68,825 |
| `PROJECT.XML` | 249 |

`ROOT.CDB` SHA-256 is
`c2d99055e02aa1fdfda3d89ef7acb11bf89863c9604d32ce3f5b1dbad30baea0`.
The decoded ROOT.DSN object stream is 2,714 bytes, contains 12 active
`$TERBIDIR` records and 12 WIRE records, and ends in donor shape `00 FF`.

## Complete component/attachment order

One package contains independently positioned `:A` and `:B` flip-flops. The
stream is not a whole-package terminal-leading block and not a whole-package
component-first attachment tail. It is exactly:

```text
A terminals: 5, 6, 4, 1, 3, 2
A component record
A WIREs:     2, 5, 3, 6, 4, 1
B terminals: 12, 11, 9, 8, 10, 13
B component record
B WIREs:     12, 9, 11, 8, 10, 13
FF
```

The `2_74HC74.pdsprj` and `4_74HC74.pdsprj` donors prove that the complete
two-subpart block repeats sequentially with the next package's first terminal
immediately after the preceding package's final B WIRE. They provide direct
scaling evidence through 4x, but do not by themselves establish 9x/15x.

## Pin/link/geometry facts

The donor has two body anchors:

| Subpart | Anchor |
| --- | ---: |
| A | (-10,922,000, 7,874,000) |
| B | (-10,922,000, 4,572,000) |

Using B as the component anchor, A's donor-relative anchor delta is
`(0, 3,302,000)`. The component placer can independently beautify current
`:A` and `:B`, so every pin must use its own current subpart anchor and this
donor-relative delta.

The component pin-link fields are six consecutive 4-byte slots at the end of
each current subpart record. Their donor-proven offsets are:

| Pin | Subpart | Slot from subpart end |
| ---: | :---: | ---: |
| 2 | A | -24 |
| 5 | A | -20 |
| 3 | A | -16 |
| 6 | A | -12 |
| 4 | A | -8 |
| 1 | A | -4 |
| 12 | B | -24 |
| 9 | B | -20 |
| 11 | B | -16 |
| 8 | B | -12 |
| 10 | B | -8 |
| 13 | B | -4 |

All active terminal/component fields use `01 00`. WIRE contacts are
donor-proven zero-length units exactly on the grid-aligned component pin. The
shared validation must therefore allow zero-length only when this profile
explicitly records it; no generic family may inherit that exception.

## Current locked-mega comparison and required repair

The locked component placer emits a clean 810-byte packet as `U45:A` and
`U45:B`, with no terminal or WIRE records. It opens normally as a no-terminal
control. The existing catalogue geometry is a one-anchor cache from an older
donor and has no clean-packet active link offsets, so the current shared placer
correctly refuses it rather than guessing:

`74HC74 U45 pin 2 lacks catalogue component-link offset for clean bare-packet emission.`

The necessary implementation is additive and generic: a catalogue-declared
subpart attachment-block serializer must preserve each current subpart record,
place the donor-ordered terminals before it, append the donor-ordered WIREs,
and rebase terminal/component links only after final ROOT.DSN addresses are
known. The implementation must keep all frozen two-pin, DIL14 quad-gate, and
HC04 routes byte-stable.

## Complete first-emission comparison — 2026-07-13

The first shared-emitter probe was deliberately loader-gated before any scale
generation. Proteus raised `VGDVC.DLL` while opening it. A full record-boundary
comparison found one structural difference after every expected coordinate,
reference-width, terminal-label, CDB-row, pin-link, and final-address suffix
difference had been accounted for:

```text
actual donor A/B WIRE block:
  component-pin-link trailer + 00 + WIRE[0] + 00 + WIRE[1] + ... + 00 + WIRE[5] + next object

first probe A/B WIRE block:
  component-pin-link trailer + WIRE[0] + 00 + WIRE[1] + ... + 00 + WIRE[5] + next object
```

`WIRE[n]` here means the 49-byte `NATIVE_WIRE_PREFIX + point coordinates`
payload. The zero immediately after the pin-link trailer is a component/WIRE
record boundary. The zero between adjacent WIRE payloads is a distinct shared
WIRE separator; the actual donor has no byte between its final WIRE's
coordinates and the next terminal/finalizer. The clean mega packet omits the
component/WIRE boundary because its `:A`/`:B` component records are originally
contiguous. The first shared probe therefore began the WIRE one byte early in
**each** `:A`/`:B` block. Its prior `00 + WIRE[n]` unit form also inserted the
wrong leading separator before each first WIRE, so the two findings must be
applied together: add the declared component/WIRE zero, then strip the
per-unit leading zero only from WIRE[0].

The subsequent loader probe still failed, so the full tail was compared from
the final `74HC74` marker rather than only from the WIRE boundary. The manual
donor has nine zero bytes between the component object ID and its six active
four-byte pin-link fields. The locked mega clean packet has ten. Its terminal
planner therefore initially placed the six links one byte later than the
accepted packet after allowing for the wider `U45:A` reference. This is a
clean-packet reserved-padding difference, not a terminal or WIRE coordinate
difference. The profile must remove exactly that one declared zero immediately
before the contiguous active link array, then append the component/WIRE
boundary zero described above. That preserves the six link slots as `-24`
through `-4` from the normalized current subpart end.

The terminal record templates themselves are not the discrepancy: after their
documented symbol/label coordinates and active final-address suffixes are
masked, all fixed terminal fields match the donor. The current U45 CDB rows
also preserve the locked-mega packet's current IDs and are valid in the bare
no-terminal control. The pin-link slots and final-address formula likewise
match the donor's 12 terminal/WIRE associations.

The evidence-backed generic repair is catalogued as
`subpart_component_wire_separator_policy = append_single_zero` plus
`subpart_first_wire_separator_policy = strip_first_leading_separator` and
`subpart_link_prefix_zero_trim_count = 1`. The shared serializer removes the
declared clean-packet link padding, inserts the one component/WIRE boundary,
and removes only the first leading unit separator for every declared subpart
block; it preserves leading separators on subsequent WIRE units. This is the
complete currently-known donor grammar set and does not modify any accepted
family route.
