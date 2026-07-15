# 38-family mixed expansion: missing-seven donor preflight

Date: 2026-07-15

## Scope and freeze

This is an additive investigation from the user-accepted 38-family `I18`
CTRL+S stream. No accepted two-pin, BJT/control, or existing catalogue-family
geometry is changed by this work. The purpose is to add the seven components
that were absent from the previous 49-family mix before touching the gate
families: `NE555`, `LM741`, `74HC74`, `7SEG-COM-AN-BLUE`,
`7SEG-COM-CAT-BLUE`, `BRIDGE`, and `TRAN-2P2S`.

All facts below come from the actual user-terminalized donor projects. The
component catalogue is a normalized cache of these facts, not a replacement
for the donors.

## Complete project inventory

Every project has exactly these archive members:

`SCRIPTS/PWRRAILS.DAT` (17 B), `ROOT.CDB`, `ROOT.DSN`, and `PROJECT.XML`
(249 B). Each `ROOT.CDB` has one selected package pin row and one matching
property row; the selected package is `U1` for `NE555`, `LM741`, and `74HC74`,
`D1` for both displays, `D1` for `BRIDGE`, and `T1` for `TRAN-2P2S`.
There is no user Ctrl+S comparison pair for these donors, so no CDB mutation
is inferred or emitted from them.

| Family | Authoritative terminal donor | DSN / CDB bytes | Object bytes | Terminal / WIRE count | Final object bytes |
|---|---|---:|---:|---:|---|
| NE555 | `proteus_ic/donors/terminalized_catalogue_evidence/dil8_analog_ic/NE555/NE555_terminalized_primary.pdsprj` | 67,552 / 300 | 1,681 | 8 / 8 | `...ff` |
| LM741 | `proteus_ic/donors/terminalized_catalogue_evidence/dil8_analog_ic/LM741/LM741_terminalized_primary.pdsprj` | 67,880 / 358 | 1,548 | 7 / 7 | `...ff` |
| 74HC74 | `proteus_ic/donors/terminalized_catalogue_evidence/dil14_dual_d_ff/74HC74/74HC74_terminalized_primary.pdsprj` | 68,825 / 374 | 2,714 | 12 / 12 | `...ff` |
| 7SEG-COM-AN-BLUE | `proteus_ic/donors/terminalized_catalogue_evidence/display_7seg/7SEG-COM-AN-BLUE/7SEG-COM-AN-BLUE_user_terminalized_july04.pdsprj` | 109,163 / 322 | 2,034 | 8 / 8 | `...ffff` |
| 7SEG-COM-CAT-BLUE | `proteus_ic/donors/terminalized_catalogue_evidence/display_7seg/7SEG-COM-CAT-BLUE/7SEG-COM-CAT-BLUE_user_terminalized_july04.pdsprj` | 109,549 / 381 | 2,420 | 8 / 8 | `...ffff` |
| BRIDGE | `proteus_ic/donors/terminalized_catalogue_evidence/four_pin_rectifier_transformer/BRIDGE/BRIDGE_user_terminalized_july04.pdsprj` | 146,583 / 255 | 1,008 | 4 / 4 | `...ffff` |
| TRAN-2P2S | `proteus_ic/donors/terminalized_catalogue_evidence/four_pin_rectifier_transformer/TRAN-2P2S/TRAN-2P2S_user_terminalized_july04.pdsprj` | 146,627 / 279 | 1,052 | 4 / 4 | `...ffff` |

For every terminal in every donor, the suffix equals the low 16 bits of the
absolute byte immediately before its associated WIRE marker. All component
pin links use active `0100` trailers except `BRIDGE` and `TRAN-2P2S`, which
use active `0200`. The unified emitter must allocate these suffixes only after
the final ROOT.DSN stream is assembled.

## Relative pin frames and orientations

The tuples below are `(x, y)` offsets from the stated component marker anchor;
the complete per-pin link offsets, labels, roles, and evidence paths are in
`knowledge/component_catalog_v0.json`. Left pins are `1800`; right pins are
`0`.

| Family | Marker anchor | Relative pins (offset / side) |
|---|---|---|
| NE555 | `(-9906000, 4572000)` | `1=(0,-1778000)/L; 2=(-1270000,-1016000)/L; 3=(1270000,1016000)/R; 4=(-1270000,1016000)/L; 5=(-1270000,0)/L; 6=(1270000,-1016000)/R; 7=(1270000,508000)/R; 8=(0,1778000)/L` |
| LM741 | `(-9652000, 6604000)` | `1=(0,1016000)/R; 2=(-1016000,-254000)/L; 3=(-1016000,254000)/L; 4=(-254000,-1016000)/L; 5=(0,-1016000)/R; 6=(1016000,0)/R; 7=(-254000,1016000)/L` |
| 74HC74 | `(-10922000, 4572000)` (B subpart) | `1=(762000,1270000)/L; 2=(-508000,3048000)/L; 3=(-508000,2540000)/L; 4=(762000,3810000)/L; 5=(2032000,3048000)/R; 6=(2032000,2032000)/R; 8=(2032000,-1270000)/R; 9=(2032000,-254000)/R; 10=(762000,508000)/L; 11=(-508000,-762000)/L; 12=(-508000,-254000)/L; 13=(762000,-2032000)/L` |
| 7SEG-COM-AN-BLUE | `(-6329680,-2011680)` | `CommonAnode=(2433320,3322320)/R; a..g=(655320,2560320..1036320 step -254000)/L` |
| 7SEG-COM-CAT-BLUE | `(-6329680,-5080000)` | `a..g=(-254000,-254000..-1778000 step -254000)/L; commoncath=(1249680,-2667000)/R` |
| BRIDGE | `(-6350000,-3789680)` | `BOTTOM=(-254000,-1016000)/R; LEFT=(-1016000,0)/L; RIGHT=(1016000,0)/R; TOP=(0,1016000)/R` |
| TRAN-2P2S | `(-6329680,-2265680)` | `BOTTOMLEFT=(-508000,-2286000)/L; BOTTOMRIGHT=(2032000,-2286000)/R; TOPLEFT=(-508000,-254000)/L; TOPRIGHT=(2032000,-254000)/R` |

## Verified terminal/unit serialization

`NE555` and `LM741` use the already-supported
`terminal_leading_component_then_wires` grammar. Their exact donor terminal
and WIRE pin orders are respectively:

- `NE555`: terminal `3,7,6,1,8,4,5,2`; WIRE `4,7,3,1,8,2,6,5`.
- `LM741`: terminal `6,1,7,5,4,3,2`; WIRE `3,2,6,7,4,1,5`.

`74HC74` uses the existing `subpart_terminal_component_wires` grammar:
subpart A terminal order `5,6,4,1,3,2`, WIRE order `2,5,3,6,4,1`; subpart B
terminal order `12,11,9,8,10,13`, WIRE order `12,9,11,8,10,13`.

The display, bridge, and transformer donors keep their component packet in the
stream followed by immediate terminal/WIRE units. Their donor unit orders are:

- 7SEG anode: `CommonAnode,a,b,c,g,d,e,f`.
- 7SEG cathode: `commoncath,a,b,c,d,e,f,g`.
- BRIDGE: `RIGHT,TOP,BOTTOM,LEFT`.
- TRAN-2P2S: `TOPRIGHT,BOTTOMRIGHT,TOPLEFT,BOTTOMLEFT`.

Their WIREs are nonzero, donor-proven polylines from a grid contact to the
exact pin. The general mixed route will retain that topology/order when it is
available and otherwise may retarget it only to the current component's
grid-aligned contact and exact current pin; it must never replace it with a
standalone side-terminal or label-only route.

## Additive implementation plan

1. Add a visual-only `layout.front_families` placement option so the just-added
   family appears at the visible front without changing ROOT.DSN packet order.
2. Promote `NE555` first: add only its donor-proven active trailer and WIRE
   order to the shared totalmix profile; it requires no new alternate emitter.
3. Rebuild the I18 38-family baseline plus NE555 with a compact shelf, force
   grid-contact/nonzero-WIRE mode, static audit, and local normal/cold loader
   gate before moving to the next family.
4. Keep the other six donor facts catalogued but untouched until the preceding
   candidate has passed. No prior accepted family is retargeted.

## NE555 39-family result

`experiments/totalmix_38_growth_missing7_v1_temp_2026_07_15/01_ne555_39f`
was freshly placed from the locked mega with the 38 I18 families plus `NE555`.
The layout is deliberately test-only compact: 50,000,000-unit shelf,
interleaved families, grid-preserving translation, and `front_families` set to
`NE555`. It generated 39 component packets, 186 active terminals, and 186
WIREs. Static checks confirm all contacts are grid aligned and each WIRE is
nonzero and touches its terminal and exact pin.

The generated NE555 terminal order is exactly
`3,7,6,1,8,4,5,2`; its WIRE order is exactly
`4,7,3,1,8,2,6,5`, matching the donor. Its final coordinates and suffixes
differ only because the freshly placed mixed stream has a new component
location and final absolute WIRE addresses; unlike the solo donor's zero-length
records, every generated NE555 WIRE is the required nonzero grid-contact to
exact-pin segment.

The disposable project `02_local_proteus_gate/G02_38F_PLUS_NE555_TERMINALIZED_1X_GATE_COPY.pdsprj`
normal-opened and cold-reopened in local Proteus after the required delayed
wait. No Bad Object Record, LXLCORE, fatal, or device-library dialog appeared,
and its SHA-256 did not change (`9A5817B300FA9E2851E27E07F527D41F855D466228B081A12E7EBAFFB1ACFCCB`).
No Ctrl+S was used.

## 74HC74 41-family result

`experiments/totalmix_38_growth_missing7_v1_temp_2026_07_15/03_74hc74_41f`
adds exactly one dual-D-flip-flop package to the committed 40-family baseline.
The shared placer emits the donor-proven A/B subpart sequence rather than a
generic all-pins tail: each subpart receives its active terminals, component
packet links, and WIREs together. The new package is fronted in the compact
visual shelf without changing the mixed packet order.

Static validation passed: 41 components, 205 active terminal/WIRE pairs,
grid-aligned contacts, and nonzero terminal-to-exact-pin WIREs. The donor's
zero-length subpart records are intentionally retargeted to the required
nonzero grid-contact segments for the mixed route; pin/link offsets, active
`0100` trailer, A/B block order, terminal labels, and final-address suffix
rebase remain donor-proven.

The disposable local gate copy normal-opened and cold-reopened without a
modal error or hash mutation (`E78F4361E3AFEE776168EB8FC68D743ABF23CE1E684E1F3565EA6657E0C5F28E`).
No Ctrl+S was used.

## LM741 40-family result

`experiments/totalmix_38_growth_missing7_v1_temp_2026_07_15/02_lm741_40f`
was freshly placed from the same locked mega with the 39-family NE555 result
plus `LM741`. `LM741` is fronted at visual slot zero under the same compact,
grid-preserving 50,000,000-unit test shelf. Static validation reports 40
selected components, 193 active terminal/WIRE pairs, grid-aligned contacts,
and nonzero terminal-to-exact-pin WIREs.

Its generated terminal order is exactly `6,1,7,5,4,3,2` and its WIRE order is
exactly `3,2,6,7,4,1,5`, matching the authoritative donor. Differences from
the donor are limited to expected freshly placed coordinates, final-address
suffixes, the locked-mega component packet form, and the deliberately nonzero
mixed WIRE segments.

The disposable gate copy normal-opened and cold-reopened in local Proteus with
no Bad Object Record, LXLCORE, fatal, or library dialog and no hash mutation:
`19B1E71FF2D224F7A9D555C68EBDF1ABA9C6CDC6A1B71A5AC3BC873AEC90EF1D`.
No Ctrl+S was used.
