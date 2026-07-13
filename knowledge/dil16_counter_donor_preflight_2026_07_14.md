# DIL16 counter donor preflight — 2026-07-14

## Authority and scope

This note is the pre-implementation audit for the `dil16_counter` families
`74HC160` and `74HC192`. The authoritative terminalized donors are:

- `proteus_ic/donors/terminalized_catalogue_evidence/dil16_counter/74HC160/74HC160_terminalized_primary.pdsprj`
- `proteus_ic/donors/terminalized_catalogue_evidence/dil16_counter/74HC192/74HC192_terminalized_primary.pdsprj`

Fresh component-placer controls were produced only from the locked mega donor:
`proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`.
No terminalized donor packet will be copied into a generated output.

## Complete archive inventory

| Family | Archive SHA-256 | `ROOT.DSN` bytes / SHA-256 | `ROOT.CDB` bytes / SHA-256 | Other members |
| --- | --- | --- | --- | --- |
| 74HC160 | `D93A2F35B925299D451B2DE8CE4D4584B9A44F272BD27338D0749B10FE93137C` | 68,888 / `755D85921D9626192FCC992D6E9BD4FD6B4094758DD1603C0E0C7F23B6BD7684` | 360 / `2090F2ECFA4FEC145BB257B6E8F0DAFE9ED647CB0EC75705DC8C9A28CDD6C728` | `SCRIPTS/PWRRAILS.DAT` (17 bytes), `PROJECT.XML` (249 bytes) |
| 74HC192 | `827A61BEBE3F0BE06E85B29B61AD0BF516E4DB34811C8902B5F4B3FD1E4054AF` | 68,902 / `E1C53618BF089571631B3AC33D39E3AA5E98329C6FF42412EF5646A5205B12F8` | 356 / `8EF57067B5D3BFAE69A15B54B7135E8F2B126E78149264BE2E8CC1A3389414A4` | `SCRIPTS/PWRRAILS.DAT` (17 bytes), `PROJECT.XML` (249 bytes) |

Each donor CDB has one `U1` pin row and one `U1` property row. It is evidence
only: active terminal work preserves the fresh locked-mega control's `ROOT.CDB`
unchanged and does not copy or mutate donor CDB data.

## ROOT.DSN frame grammar

Both donors use the same complete terminal-leading stream:

`14 BIDIR terminals -> 00 separator -> 445-byte component packet -> 14 WIRE records -> explicit FF`.

| Family | Object chunk start | Object chunk bytes | Component range | WIRE range | WIRE record bytes | Final tail |
| --- | ---: | ---: | --- | --- | ---: | --- |
| 74HC160 | 65,305 | 2,686 | offset 1,540..1,985 | 1,985..2,685 | 50 | `00 FF` |
| 74HC192 | 65,323 | 2,682 | offset 1,536..1,981 | 1,981..2,681 | 50 | `00 FF` |

The terminal and WIRE suffixes obey the accepted final-address rule exactly:
`(ROOT.DSN object-chunk absolute start + WIRE marker offset - 24) & 0xffff`.
The component packet contains fourteen `suffix + 0100` link fields at offsets
`-64, -60, ... -12` from its final byte. Their donor positions are offsets
381..433 in the 445-byte packet.

The donor `SUBCKT NAME` field has a zero-length payload, as does the fresh
locked-mega packet. There is no metadata-removal rule for either family.

## Fresh locked-mega controls and all explained deltas

| Family | Control | Project SHA-256 | Selected ref | Raw group data | Live donor packet | Explained delta |
| --- | --- | --- | --- | ---: | ---: | --- |
| 74HC160 | `00_preflight_controls/74HC160_1x_locked_mega_control.pdsprj` | `B1504C1B826C417702DB2991CD919D55841B915D37C2305872E1DCD19046E435` | `U29` | 446 | 445 | one extra raw generator-tail `00`; ref text and translated coordinates are expected placed-design differences; fourteen blank link slots need donor-proven active `0100` links |
| 74HC192 | `00_preflight_controls/74HC192_1x_locked_mega_control.pdsprj` | `72998A640DDE0A8B6C599E7902D97D0941257F53017CC3EA9860D753DDF6FD3F` | `U21` | 446 | 445 | one extra raw generator-tail `00`; ref text and translated coordinates are expected placed-design differences; fourteen blank link slots need donor-proven active `0100` links |

The control object chunks are `00 00 + raw group + FF`. Trimming only the
extra raw group-tail produces the donor-proven 445-byte live packet width. The
emitter must keep the placed packet's own body, reference, and coordinates; it
may patch only the evidence-backed end-relative link slots and then rebase them
from final WIRE addresses.

## Terminal and pin evidence

Both donors have fourteen terminals, on-grid terminal contacts, `1800` on left
pins and `0` on right pins. Their WIRE records are all zero length: each starts
and ends at the pin/contact. They prove record grammar, terminal order,
orientation, link slots, pin geometry, and WIRE ordering, but are not an active
output template. The generated route must retain those facts while moving each
terminal contact one grid step outward and creating a nonzero short WIRE to the
calculated exact pin.

`74HC160` terminal-record order:

`3, 4, 5, 6, 7, 10, 2, 9, 1, 14, 13, 12, 11, 15`.

Its WIRE/link order is:

`3, 14, 4, 13, 5, 12, 6, 11, 15, 7, 10, 2, 9, 1`.

`74HC192` terminal-record order:

`3, 2, 6, 7, 12, 13, 15, 1, 10, 9, 5, 4, 11, 14`.

Its WIRE/link order is:

`15, 3, 1, 2, 10, 6, 9, 7, 5, 12, 4, 13, 11, 14`.

The `74HC192` donor text calls the CPU/UP terminal `UP PIN 9`, even though it
occupies the left-side pin-5 geometry. The existing catalogue correctly uses
the user-verified/official pin identity `UP PIN 5`, while retaining the donor
record position and geometry. TI's current 74HC192 datasheet and Nexperia's
74HC193-compatible pin table both identify CPU/UP as pin 5 and D3 as pin 9.

## Implementation boundary

The shared placer already has the generic
`terminal_leading_component_then_wires` serializer used by the separately
researched 7447 route. The additive catalogue facts required here are: that
grammar, the above terminal orders, `-64..-12` component-link offsets with
`0100` trailers, one-grid-step outward contacts, nonzero contact-to-exact-pin
WIRE coordinates, explicit single-FF finalizer, and a profile-gated raw-tail
trim. No accepted family profile or shared emission branch needs alteration.

Required staged proof remains: native contact, grid contact, then active
short-WIRE/link output, each cold-opened locally before any scale work.
