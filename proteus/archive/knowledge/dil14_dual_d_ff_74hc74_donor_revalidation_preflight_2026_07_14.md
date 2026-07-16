# 74HC74 terminal-route donor preflight — 2026-07-14

## Authority and archive audit

The authoritative accepted donor is
`proteus_ic/donors/terminalized_catalogue_evidence/dil14_dual_d_ff/74HC74/74HC74_terminalized_primary.pdsprj`.
Project SHA-256:
`4586a951bbfd986c6c10e629d0a6ae8e1723a50139cdebf10fb6d383c2ee07cc`.

| Member | Bytes | SHA-256 |
| --- | ---: | --- |
| `SCRIPTS/PWRRAILS.DAT` | 17 | `1381cf6c26c8fc808c265e1c3affeedaf4041454d2ed843a9df56f67871776d7` |
| `ROOT.CDB` | 374 | `c2d99055e02aa1fdfda3d89ef7acb11bf89863c9604d32ce3f5b1dbad30baea0` |
| `ROOT.DSN` | 68825 | `36d6976c0042cb04b653c1a999be9fa70410256a3086b643d73c52d477a0a4e5` |
| `PROJECT.XML` | 249 | `2aaeba567d2046c10549d6724c8f66443455cf8c80fef0ffa35e0807b838139f` |

`ROOT.CDB` contains the `U1:A`, `U1:B`, and package-level `U1` entries.

## ROOT.DSN object grammar

The 2714-byte object stream ends in a single `FF`, has twelve active
`$TERBIDIR` records, twelve `WIRE` records, and two component records:
`U1:A` at offset 653 and `U1:B` at 2010. It is not a
component-stream-first route.

The exact donor sequence is:

1. A terminals `5, 6, 4, 1, 3, 2`.
2. `U1:A` component record.
3. A WIREs `2, 5, 3, 6, 4, 1`.
4. B terminals `12, 11, 9, 8, 10, 13`.
5. `U1:B` component record.
6. B WIREs `12, 9, 11, 8, 10, 13`.

All terminal contacts are Proteus-grid aligned. Inputs are at `1800`, outputs
at `0`, and every terminal uses trailer `0100` matching its component-link
field. The donor's twelve WIRE records are two-point, zero-length on-pin
records. The terminal link slots are a contiguous six-slot table per subpart;
the catalogue's A offsets are `-24,-20,-16,-12,-8,-4` for pins
`2,5,3,6,4,1`, and B has the equivalent table for `12,9,11,8,10,13`.

## Required staged proof

The locked mega is the sole component placer. Before accepting a new route:

1. generate a bare locked-mega 1x control;
2. cold-open direct native contacts;
3. cold-open grid-contact terminals;
4. emit the donor-proven block grammar, then verify that the final terminal
   contacts, active suffixes, and WIRE paths meet the current shared terminal
   contract.

The zero-length donor WIRE data is a research fact, not approval to regress
the system to label-only or unattached terminals. The final output must be
checked against the user-required grid-contact/short-attachment behavior and
the authoritative donor's stream, link, record-boundary, and CDB grammar.
No accepted family is altered during this work.

## Loader-stage failure analysis and correction

The first generated native/grid diagnostics used twelve inactive terminal
records (suffix `0000`), retained the bare component pin-link zeros, omitted
all twelve WIRE records, and retained the one-byte subpart link-prefix padding.
Both projects raised `Fatal Error: Internal Exception: access violation in
module 'VGDVC.DLL' [000190DA]`. The locked-mega control and a disposable copy
of the authoritative donor both opened normally, so this is a packet-grammar
failure rather than a component-placer or local-installation failure.

The full donor comparison explained every structural difference from a valid
unit: active terminal suffix + active component pin link + adjacent WIRE are
inseparable for this subpart stream; each component segment also removes the
one donor-proven pre-link zero before its active six-slot link table. The
catalogue therefore declares `staged_contact_requires_active_attachment_unit`.
The shared placer uses the existing subpart terminal/component/WIRE emitter for
both contact diagnostics. Native contact emits donor-proven zero-length WIREs
at each pin; grid contact emits the required nonzero grid-to-pin WIREs.

After that bounded shared-emitter change, the native active stage, grid active
stage, complete output, and complete cold reopen each reached a normal Proteus
schematic window after the required delayed check, without a modal dialog or a
copy hash change. The native stage is diagnostic-only and intentionally
off-grid; the final grid/complete output has twelve grid-aligned terminal
contacts and twelve nonzero exact-pin WIREs.
