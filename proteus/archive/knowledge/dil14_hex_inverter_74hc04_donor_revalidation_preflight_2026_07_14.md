# 74HC04 terminal-route donor preflight — 2026-07-14

## Scope and authority

This note covers only `74HC04`; accepted two-pin and DIL14 quad-gate routes
are not modified.  The authoritative accepted project is
`proteus_ic/donors/terminalized_catalogue_evidence/dil14_hex_inverter/74HC04/E04_74HC04_1X_NO_TERMINAL_CONTROL.pdsprj`.
Its project SHA-256 is
`db2a01276ec0cefe23e0d546e631cf126dc07a1a78fcfa13e163a13f7a229940`.

Archive-member audit:

- `PWRRAILS`: 17 bytes, SHA-256 `1381cf`…`76d7`.
- `ROOT.CDB`: 498 bytes, SHA-256 `a54c47669fc20cb5bc1163f52f7b5e73a4a346de5feec938fdb50df840a85bd7`.
- `ROOT.DSN`: 111435 bytes, SHA-256 `7bd222e91a0a290ef5c413e7cfff6337c1653e19b7f35fac8328b6fd058ea03a`.
- `PROJECT.XML`: 249 bytes, SHA-256 `543b540281bde9a8cf9aff117b648b05d372f7d00c54a5c421204739a8e2b78a`.

The DSN object stream spans the six component records `U61:A` … `U61:F`,
twelve `$TERBIDIR` records, twelve immediate `WIRE` records, and the donor's
double-`FF` finalizer.  CDB contains the six subpart rows plus the package row.

## Donor-proven attachment facts

The attachment order is:

`2, 10, 6, 4, 8, 12, 1, 11, 5, 3, 9, 13`.

The output-side units are routed three-point paths.  The input side uses a
four/three/four/four/four/four point pattern for pins
`1, 11, 5, 3, 9, 13` respectively.  Every terminal contact is grid-aligned;
left inputs use `1800`, right outputs use `0`, and each record carries the
same active suffix as its component pin-link field with trailer `0100`.

The physical component-record link slots in the accepted donor are:

| Record | Donor slots | Electrical pins |
| --- | --- | --- |
| `U61:A` | `-9`, `-5` | 1, 2 |
| `U61:B` | `-9`, `-5` | 3, 4 |
| `U61:C` | `-9`, `-5` | 5, 6 |
| `U61:D` | `-9`, `-5` | 13, 12 |
| `U61:E` | `-9`, `-5` | 11, 10 |
| `U61:F` | `-9`, `-5` | 9, 8 |

The distinction for `D` and `F` is byte- and geometry-proven.  Proteus's
internal subpart record order is not the usual human pin-to-letter order.
The catalogue must therefore bind pins 13/12 to the `D` record/anchor and
pins 9/8 to the `F` record/anchor, while retaining their normalized pin roles.

## Locked-mega control and current diagnostic

The sole placement source is
`proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`.
Its fresh 1x control selected `U202:A` … `U202:F` with a 2280-byte bare group
and a normal CDB package row.  The current catalogue diagnostic emitted all
12 records and 12 WIREs, but showed the old incorrect mapping: pins 8/9 wrote
the `U202:D` slots and pins 12/13 wrote the `U202:F` slots.  This differs from
the accepted donor in both the active component-link fields and the terminal
geometry.  It is not a final candidate.

## Evidence-backed repair set

Only the 74HC04 profile will change:

1. Swap the record/anchor assignment of pin pair 8/9 with pair 12/13 in the
   catalogue's `pin_subparts`, `component_link_subpart_end_offsets`, and
   pin geometry `component_anchor_index` fields.
2. Keep the proven `-9` input / `-5` output offsets and `0100` link trailer.
3. Preserve the donor's labels, terminal contacts, angles, WIRE coordinates,
   attachment order, stream order, CDB policy, and double-`FF` finalizer.

No shared terminal-emitter algorithm, accepted family profile, donor, or
component-placer route is changed by this repair.  A fresh staged 1x sequence
and then 9x/15x regression must pass before the profile is promoted.
