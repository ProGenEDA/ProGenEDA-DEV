# 74HC266 authoritative donor revalidation — 2026-07-14

## Scope and source of truth

This note audits the actual user-accepted Proteus project before any HC266
terminal emission. The only authoritative terminal source is
`proteus_ic/donors/terminalized_catalogue_evidence/dil14_quad_2input_logic/74HC266/74HC266_user_terminalized_july04.pdsprj`
(project SHA-256
`0e87991e5206e52ca782a35b7d8e23d236f0102cbbbc735eadf1d9eb44a60c90`).
The locked mega remains the component-placement control only; it is not a
terminal donor.

The ZIP archive is complete and contains exactly:

| member | uncompressed bytes | SHA-256 |
| --- | ---: | --- |
| `SCRIPTS/PWRRAILS.DAT` | 17 | `1381cf6c26c8fc808c265e1c3affeedaf4041454d2ed843a9df56f67871776d7` |
| `ROOT.CDB` | 425 | `9c441ae021f54cebbb5a1507f905c18a47a2bfc6c3bbb8c3130f25272491b25c` |
| `ROOT.DSN` | 110639 | `cf515b2a072e8f0bf966366daf6e167cc7f3d5cf0c74b870e6a0a2fb90203330` |
| `PROJECT.XML` | 249 | `ac14abccfc564c50085de9347d608e8cbad453c7304a7404bee7716313782907` |

`ROOT.CDB` parses as four pin rows (`U77:A`, `U77:B`, `U77:C`, `U77:D`) and
one normalized package property row (`U77`), with a 20-byte property header.
Its four subpart rows are required for a generated one-package CDB.

## Complete ROOT.DSN object-stream evidence

`ROOT.DSN` object data spans absolute offsets `106232..109742`, yielding a
3510-byte object chunk. It has four HC266 component packets at object offsets
`2`, `389`, `776`, and `1163`, ending at `389`, `776`, `1163`, and `1550`.
The component stream is followed directly by twelve terminal/WIRE attachment
units and a single `FF` finalizer: no terminal-leading or donor-packet-copy
path is permitted.

The exact attachment order, terminal contact, and full WIRE point counts are:

| pin | donor label | side/angle | terminal contact | full WIRE points |
| ---: | --- | --- | --- | --- |
| 3 | `Pin3O1` | right / 0 | `(-4064000, -2540000)` | `(-4170680,-2519680) → (-4170680,-2540000) → (-4064000,-2540000)` |
| 4 | `Pin4O2` | right / 0 | `(-4064000, -4318000)` | `(-4170680,-4297680) → (-4170680,-4318000) → (-4064000,-4318000)` |
| 10 | `Pin10O3` | right / 0 | `(0, -2540000)` | `(-106680,-2519680) → (-106680,-2540000) → (0,-2540000)` |
| 11 | `Pin11O4` | right / 0 | `(0, -4318000)` | `(-106680,-4297680) → (-106680,-4318000) → (0,-4318000)` |
| 1 | `Pin1I1` | left / 1800 | `(-6858000, -2286000)` | `(-6710680,-2265680) → (-6710680,-2286000) → (-6858000,-2286000)` |
| 2 | `Pin2I2` | left / 1800 | `(-6858000, -2794000)` | `(-6710680,-2773680) → (-6710680,-2794000) → (-6858000,-2794000)` |
| 5 | `Pin5I3` | left / 1800 | `(-6858000, -4064000)` | `(-6710680,-4043680) → (-6858000,-4064000)` |
| 6 | `Pin5I4` | left / 1800 | `(-6858000, -4572000)` | `(-6710680,-4551680) → (-6858000,-4572000)` |
| 8 | `Pin8I5` | left / 1800 | `(-2794000, -2286000)` | `(-2646680,-2265680) → (-2646680,-2286000) → (-2794000,-2286000)` |
| 9 | `Pin9I6` | left / 1800 | `(-2794000, -2794000)` | `(-2646680,-2773680) → (-2646680,-2794000) → (-2794000,-2794000)` |
| 12 | `Pin12I7` | left / 1800 | `(-2794000, -4064000)` | `(-2646680,-4043680) → (-2646680,-4064000) → (-2794000,-4064000)` |
| 13 | `Pin13I8` | left / 1800 | `(-2794000, -4572000)` | `(-2646680,-4551680) → (-2794000,-4572000)` |

The donor's label for physical pin 6 is literally `Pin5I4`; it is retained as
authoritative terminal text while the catalogue's normalized pin identity
remains pin `6`, role `2B`. All terminal contacts are at grid intersections.
Every WIRE uses the standard preceding `01 1d ... 02` record grammar; its
low-16 final address is the active terminal/component-pin suffix.

The component links were independently read from the four packet tails. Each
matches its terminal suffix and has trailer `0100`: A pins `1/-13`, `2/-9`,
`3/-5`; B `5/-13`, `6/-9`, `4/-5`; C `8/-13`, `9/-9`, `10/-5`; D `12/-13`,
`13/-9`, `11/-5` (offsets are relative to that subpart packet's end).

## Complete donor-versus-catalogue delta

All existing terminal coordinates, sides, component-link offsets, terminal
record grammar, package ordering, and 2-point paths for pins 5, 6, and 13
already match. The former catalogue was incomplete in exactly ten ways:

1. It truncated the final exact-pin point from WIRE paths for pins
   `3, 4, 10, 11, 1, 2, 8, 9, 12`.
2. It exposed `Pin6I4` as the emitted pin-6 label even though the actual donor
   serializes `Pin5I4`.

No shared-emitter algorithm change is indicated. The additive repair is
therefore limited to the HC266 catalogue profile: authoritative provenance,
donor attachment order, the nine full polylines, and the exact pin-6 terminal
label. It must then use the existing shared
`attach_catalogue_pin_bidir_terminals_to_project` path against a fresh locked
mega component-placer output.

Before this audit, the shared placer was copied unchanged to
`backups/component_terminal_placer/component_terminal_placer_before_hc266_catalogue_20260714_0705.py`
(SHA-256 `AB995CFF5230690110C39C198FBFE5FC01E49B58BD69096D55B9AA28DBAD3BEA`).
