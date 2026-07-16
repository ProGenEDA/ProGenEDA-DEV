# 74HC76 dual-JK terminal preflight — 2026-07-14

## Authority and scope

This is Proteus-only work for the next unfinished member of the DIL16 dual-JK
group: `74HC76`. The authoritative accepted donor is
`proteus_ic/donors/terminalized_catalogue_evidence/dil16_dual_jk_ff/74HC76/74HC76_terminalized_primary.pdsprj`.
The locked component-placer donor remains
`proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`.
No earlier report overrides these project bytes.

## Complete donor facts

| Item | Value |
| --- | --- |
| Archive SHA-256 | `11BDD4B0EC440ED0B49AAB82606C1B5F55A3D3B30A74ACD63290F4733840B6A8` |
| Archive members | `SCRIPTS/PWRRAILS.DAT` (17), `ROOT.CDB` (384), `ROOT.DSN` (69,123), `PROJECT.XML` (249) |
| ROOT.DSN SHA-256 | `BF25A1D6E5DAC729571FAE6FD12F0C40C1219DE4FB5A37280C05ACB56F790AE1` |
| ROOT.CDB SHA-256 | `DFA8549EE714667111DCAD9A234B3963AD2A03624FB68044DA3AB27684AB413B` |
| ROOT.DSN object stream | absolute start `65,184`, length `3,042`, explicit final `FF` |

The donor has fourteen `$TERBIDIR` records and fourteen WIRE records. Its
multipart grammar is asymmetric and must remain so:

`12 terminal records -> 00 -> U1:A -> 7 WIREs -> 2 terminal records -> 00 -> U1:B -> 7 WIREs -> FF`.

The exact terminal order is
`15,14,11,10,4,1,16,9,6,12,3,2,7,8`; the WIRE/link order is
`4,15,1,16,14,2,3,9,11,6,12,10,7,8`. Every donor WIRE is zero-length and is
evidence for stream grammar, order, orientation, link position, and exact pin
endpoint only. The final route must use a nonzero short WIRE from an on-grid
terminal contact to that exact pin.

The terminal labels/angles are donor-derived. Pins `5` and `13` are hidden
power pins; visible pins use left `1800` or right `0` orientation. The
catalogue records every component-anchor-relative coordinate, subpart (`A` or
`B`), WIRE order, and end-relative four-byte pin-link slot.

## Fresh locked-mega control comparison

A fresh one-part component-placer control selects package `U41`, with physical
subparts `U41:A` and `U41:B`; its raw selected group is 818 bytes. `ROOT.CDB`
contains both fresh subpart references. Its live packet must retain those
references and both complete subpart records. The accepted donor uses `U1:A`
and `U1:B`, so reference width/coordinates and active-vs-zeroed link suffixes
are expected deltas, not a donor-copy instruction.

The one donor-proven packet normalization is already catalogue-declared:
each locked-mega subpart has one zero byte immediately before its contiguous
reserved link array. The shared subpart serializer removes exactly that padding
when it activates the links; it preserves the component data, subpart order,
terminal blocks, finalizer, and `ROOT.CDB`. No new terminal emitter, component
generator, or CDB mutation is authorized.

## Plan

Regenerate the 1x locked-mega control and use only
`src/proteusgen/component_terminal_placer.py` for native-contact, grid-contact,
and active stages. Stop on a loader failure. If the 1x grid/active route passes,
regenerate 9x and 15x through the same profile, static-audit all attachment
units, and cold-open/cold-reopen them. Mixed output remains prohibited until
every group has its own solo 1x/9x/15x evidence.

## Fresh loader outcome and decision

The deliberately inactive `native_pin_contact` and `grid_contact` records
both stop at the same local `Fatal Error: Internal Exception: access violation
in module 'VGDVC.DLL' [000190DA]`. The captures are retained in
`experiments/dil16_dual_jk_ff_74hc76_terminal_v3_temp_2026_07_14/02_local_proteus_gate/`.
They contain terminal records without the donor-required active terminal/link/
WIRE attachment unit, so they are rejected diagnostics rather than repair
targets.

The independent comparison controls all normal-opened without a rewrite after
the 12-second stability period: the fresh locked-mega no-terminal 1x control,
the authoritative accepted donor, and the shared-placer complete active 1x
output. The complete active output then passed normal open and cold reopen at
9x and 15x. Static audits found `14`, `126`, and `210` terminal/WIRE units at
1x, 9x, and 15x respectively; every final terminal contact is grid-aligned,
every final WIRE is nonzero and reaches its exact pin, active suffixes are
allocated from final ROOT.DSN WIRE addresses, and ROOT.CDB is unchanged.

Conclusion: retain the existing complete shared catalogue route and record
inactive contact-only HC76 forms as negative diagnostic evidence. No new
terminal script, donor substitution, CDB edit, or change to any accepted
family is justified.
