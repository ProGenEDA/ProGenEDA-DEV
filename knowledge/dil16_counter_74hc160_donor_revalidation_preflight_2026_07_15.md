# 74HC160 donor revalidation preflight - 2026-07-15

Authoritative terminal donor:
`proteus_ic/donors/terminalized_catalogue_evidence/dil16_counter/74HC160/74HC160_terminalized_primary.pdsprj`.

Locked placement donor:
`proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`.

## Complete donor audit

The donor archive contains `SCRIPTS/PWRRAILS.DAT` (17 bytes), `ROOT.CDB`
(360 bytes), `ROOT.DSN` (68,888 bytes), and `PROJECT.XML` (249 bytes).
`ROOT.CDB` has one U1 pin/property row: 74HC160, `74XX160.MDF`, DIL16, TTLHC.
Visible pins are D0-D3 3/4/5/6, Q0-Q3 14/13/12/11, RCO 15, ENP 7, ENT 10,
CLK 2, LOAD 9, MR 1; VCC 16 and GND 8 are hidden.

The DSN object chunk starts at absolute byte 65,305, is 2,686 bytes, and ends
with an explicit donor final `FF`. It contains fourteen zero-length two-point
terminal/WIRE attachment units in this order:

`D0 PIN 3, D1 PIN 4, D2 PIN 5, D3 PIN 6, ENP PIN 7, ENT PIN 10, CLK PIN 2,
PIN 9 LOAD, MR PIN 1, Q0 PIN 14, Q1 PIN 13, Q2 PIN 12, Q3 PIN 11,
RCO PIN 15`.

The zero-length WIREs are attachment grammar evidence only. Catalogue facts
already provide the current-component marker-relative pin coordinates, left
1800/right 0 orientation, one outward grid step, direct terminal-contact-to-
exact-pin WIRE policy, component links and catalogue-leading record grammar.
No source/profile change is justified before fresh output is gated.

## Planned proof

Generate locked-mega native/grid/complete 1x diagnostics, gate them normally
and cold, then generate/gate final 9x and 15x. Require 14/126/210 nonzero
grid-aligned WIREs, final-address suffix links, normalized selected CDB, and
the preserved finalizer. Use only the shared terminal placer.

## Result

The native-contact, grid-contact, and complete 1x diagnostics all passed
normal and cold local Proteus gates with unchanged disposable copies. The
complete 9x and 15x outputs also passed both gates. Their active streams
contain respectively 126 and 210 `$TERBIDIR`/WIRE pairs; every terminal
contact is grid aligned and every WIRE is nonzero. The 74HC160 profile's
`append_explicit_single_ff` policy is correct: the final byte cannot be
interpreted as a double-FF marker because a final WIRE coordinate may itself
end in `FF`.

Focused shared counter/placement regression: `7 passed, 244 deselected`.
`python -m compileall -q src tests tools/proteus_generation` passed. No source
or catalogue profile change was required. User visual acceptance remains
separate.
