# DIL16 register donor preflight — 2026-07-14

## Authority and scope

This is the pre-implementation audit for the `74HC174` DIL16 register route.
The sole authoritative terminalized donor is:

`proteus_ic/donors/terminalized_catalogue_evidence/dil16_register/74HC174/74HC174_terminalized_primary.pdsprj`

The fresh no-terminal control was made exclusively through the locked component
placer donor:

`proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`

No terminalized donor packet, terminal record, or wire record is transplanted
into the generated project. The existing shared
`component_terminal_placer.py` route is the only intended emitter.

## Complete archive and CDB inventory

| Project | Archive SHA-256 | `ROOT.DSN` bytes / SHA-256 | `ROOT.CDB` bytes / SHA-256 |
| --- | --- | --- | --- |
| Accepted donor | `FD46EDA59A72CC398DA287A6491AF33349C1111CDE465C509325B1CA34775B50` | 68,948 / `9477C8B59B33B9213A9B22894F01B4005A1A4C9749549D3B86C5E1EA461E1BD8` | 355 / `0A440D6C79DFBAB2708674C3D301B0DB1BF4C5C6042CA583F97D0838398AF1A5` |
| Fresh locked-mega 1x control | `8E58D9FDB5E3B0DEA5689128E5D978EE2ED559C9310B09D468194E912708BF44` | 146,024 / `479A3C19BA0CD935DF577522DF3697E80D799B7D55F9DDEECA64CC17E05BF3AC` | 614,696 / `A2F28AD3E4002B5F29584C81B3CC0C6E0F6D837F926D2BF6AA44B751DC656590` |

Both projects also contain unchanged `SCRIPTS/PWRRAILS.DAT` (17 bytes) and
`PROJECT.XML` (249 bytes). The donor CDB parses as one pin row plus one
property row for `U1`; the locked mega control deliberately preserves its full
4,520 pin rows and 3,550 property rows. This route is DSN-only: generated
terminal candidates must preserve the source control's `ROOT.CDB` byte-for-byte.

## ROOT.DSN stream and packet comparison

The donor object chunk begins at absolute byte 65,370. Its full 2,681-byte
object stream is:

`14 BIDIR terminal records → 00 separator → 445-byte U1 component packet → 14 WIRE records of 50 bytes → explicit FF`.

The control object chunk begins at absolute byte 144,163. Its live U25 packet
is 446 bytes; `ComponentGroup.data` retains one additional raw finalizer `00`
for a total of 447 bytes. The terminal-leading route must consume only that
raw generator tail before appending WIREs, exactly as the accepted counter
profiles do.

After shortening the placed reference `U25` to donor-width `U1`, masking the
five existing placed-design coordinate pairs, the one object identity byte,
and the fourteen donor-active/control-blank pin-link fields, the 445-byte
component bodies compare exactly. Every delta is therefore accounted for:

- placed reference width (`U25` versus `U1`);
- five donor/locked-mega coordinate fields (including the zero-length
  `SUBCKT NAME` anchor, which remains part of its untouched placed packet);
- one existing object identity byte (`0x20` control versus `0x1b` donor);
- fourteen blank control link slots versus donor `suffix + 0100` links; and
- the generator-only raw finalizer byte.

No component text payload is removed: both donor and control have a
zero-length `SUBCKT NAME` field. The profile must keep the placed packet body,
reference, coordinates, and identity byte unchanged; it may patch only the
donor-proven end-relative pin-link slots.

## Terminal, pin, and WIRE evidence

All fourteen donor WIREs are zero-length at the physical pin. They prove stream
grammar, label/order, orientation, exact pin geometry, link slots, and final
address suffixing; they do **not** authorize zero-length generated WIREs. The
shared placer must put the terminal attaching edge on the 254,000-unit grid,
one grid step outward, then generate a nonzero short WIRE to the exact
catalogue-calculated pin.

Terminal record order is:

`2, 5, 7, 10, 12, 15, 3, 4, 6, 11, 13, 14, 9, 1`.

WIRE/link order and component-end offsets are:

| Pin | Donor label | Side / angle | Link offset | Trailer |
| ---: | --- | --- | ---: | --- |
| 3 | `D0 PIN 3` | left / 1800 | -64 | `0100` |
| 2 | `Q0 PIN 2` | right / 0 | -60 | `0100` |
| 4 | `D1 PIN 4` | left / 1800 | -56 | `0100` |
| 5 | `Q1 PIN 5` | right / 0 | -52 | `0100` |
| 6 | `D2 PIN 6` | left / 1800 | -48 | `0100` |
| 7 | `Q2 PIN 7` | right / 0 | -44 | `0100` |
| 11 | `D3 PIN 11` | left / 1800 | -40 | `0100` |
| 10 | `Q3 PIN 10` | right / 0 | -36 | `0100` |
| 13 | `D4 PIN 13` | left / 1800 | -32 | `0100` |
| 12 | `Q4 PIN 12` | right / 0 | -28 | `0100` |
| 14 | `D5 PIN 14` | left / 1800 | -24 | `0100` |
| 15 | `Q5 PIN 15` | right / 0 | -20 | `0100` |
| 9 | `CLK PIN 9` | left / 1800 | -16 | `0100` |
| 1 | `MR PIN 1` | left / 1800 | -12 | `0100` |

The existing catalogue pin coordinates are component-anchor-relative donor
measurements. The actual final terminal/component suffix is always rebased as
`(final_object_chunk_absolute_start + WIRE_marker_offset - 24) & 0xffff`.

## Additive implementation boundary

The established shared terminal-leading serializer already supports this
grammar. The additive catalogue facts are only the link offsets/trailers,
donor terminal order, finalizer/tail policy, CDB preservation, and a staged
validation cap of 15 requested by the user. No shared implementation branch or
accepted family profile is changed. Candidates must next complete the required
native-contact, grid-contact, and active 1x loader gates before any 9x or 15x
output is generated.
