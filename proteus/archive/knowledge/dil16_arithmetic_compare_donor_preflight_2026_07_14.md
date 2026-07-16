# DIL16 arithmetic/compare donor preflight — 2026-07-14

## Authority and scope

This is the complete pre-implementation audit for the `74HC283` four-bit
adder and `74HC85` four-bit comparator. The authoritative terminalized donors
are:

- `proteus_ic/donors/terminalized_catalogue_evidence/dil16_arithmetic_compare/74HC283/74HC283_terminalized_primary.pdsprj`
- `proteus_ic/donors/terminalized_catalogue_evidence/dil16_arithmetic_compare/74HC85/74HC85_terminalized_primary.pdsprj`

Fresh no-terminal controls use only the locked mega component placer donor:
`proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`.
The existing shared terminal placer is the only intended emitter; no
terminalized donor packet is copied into a generated project.

## Archive, CDB, and object-stream inventory

| Family | Donor archive SHA-256 | Donor DSN / CDB bytes | Fresh control archive SHA-256 | Control DSN / CDB bytes |
| --- | --- | ---: | --- | ---: |
| `74HC283` | `B4A233E513C9EE4867C748544BD1688AF6B26DBF911B0CFEB1744421F9E2AA10` | 69,217 / 345 | `E6CA2E83EAEC6E6924B61893BF01A7E3D763C62116E22D659A0C3E3FD7A3F769` | 146,015 / 614,696 |
| `74HC85` | `6BE3849BF14CCFEAC0F715561F6A25A1CFB10A8C3DDCC496E2355F2B4F2C1FF7` | 69,220 / 351 | `48C36A83CCCC6E9536675F1A53E8DB71B5CDF02188E4CBAF133A1251FD64A4DA` | 146,011 / 614,696 |

Every donor archive contains `SCRIPTS/PWRRAILS.DAT` (17 bytes), `ROOT.CDB`,
`ROOT.DSN`, and `PROJECT.XML` (249 bytes). Each donor CDB has exactly one pin
row and one property row for `U1`; each locked-mega control deliberately keeps
the full 4,520 pin rows and 3,550 property rows. Active terminal emission is
DSN-only and must retain the source control's `ROOT.CDB` unchanged.

Both donors use the same full grammar:

`14 BIDIR terminals → 00 separator → component packet → 14 50-byte WIRE records → explicit FF`.

| Family | DSN object chunk start / bytes | Component bytes | First WIRE offset | Component/end-relative link slots |
| --- | ---: | ---: | ---: | --- |
| `74HC283` | 65,649 / 2,671 | 436 | 1,994 | `-64, -60, …, -12`, each `0100` |
| `74HC85` | 65,647 / 2,676 | 432 | 1,999 | `-64, -60, …, -12`, each `0100` |

The fresh controls have live component widths 437 (`U17`) and 433 (`U37`)
respectively. Their `ComponentGroup.data` records retain one extra raw trailing
`00`; terminal-leading emission must consume only that raw generator tail.
After normalizing reference width to `U1`, masking five placed-design coordinate
pairs, the one existing object identity byte, and the fourteen active-versus-
blank link fields, each fresh control body compares byte-for-byte to its donor.
There are no unexplained structural deltas and no component text payload to
remove: both donor and control `SUBCKT NAME` fields are zero-length.

## Pin/link evidence

Every donor WIRE is zero length at the physical pin. It proves record order,
relative pin geometry, link slots, suffix/address relation, and orientation;
it does not permit zero-length output. The shared placer must move the terminal
attaching edge one 254,000-unit grid step outward and draw a nonzero short WIRE
back to the exact pin.

`74HC283` terminal record order:

`4, 1, 13, 10, 9, 5, 3, 14, 12, 6, 2, 15, 11, 7`.

`74HC283` WIRE/link order: `5, 3, 14, 12, 6, 2, 15, 11, 7, 9, 4, 1, 13, 10`.

`74HC85` terminal record order:

`7, 6, 5, 10, 12, 13, 15, 9, 11, 14, 1, 2, 3, 4`.

`74HC85` WIRE/link order: `10, 12, 13, 15, 9, 11, 14, 1, 2, 7, 3, 6, 4, 5`.

Existing catalogue pin geometry already records each exact component-relative
pin position, donor terminal label, side, orientation, and WIRE order. The
only new facts needed are terminal-leading stream/link/finalizer rules and the
end-relative offsets mapped from the two authoritative donors. Terminal and
component link suffixes will be rebased from final ROOT.DSN WIRE positions:
`(object_chunk_absolute_start + WIRE_marker_offset - 24) & 0xffff`.

## Additive boundary

Both families are independent profile additions to the shared terminal-leading
serializer. No accepted family profile or `component_terminal_placer.py` branch
needs changing. They must pass the three 1x diagnostic loader stages before any
9x/15x generation; per user instruction, no mixed output is made until all
remaining solo groups are complete.
