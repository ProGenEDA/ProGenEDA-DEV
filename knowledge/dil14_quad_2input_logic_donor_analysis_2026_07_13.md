# DIL14 quad 2-input logic donor analysis — 2026-07-13

Authoritative terminalized donors, all under
`proteus_ic/donors/terminalized_catalogue_evidence/dil14_quad_2input_logic/`:

- `74HC00/74HC00_user_terminalized_july04.pdsprj`
- `74HC02/74HC02_user_terminalized_july04.pdsprj`
- `74HC08/74HC08_user_terminalized_july04.pdsprj`
- `74HC32/74HC32_user_terminalized_july04.pdsprj`
- `74HC86/74HC86_user_terminalized_july04.pdsprj`
- `74HC266/74HC266_user_terminalized_july04.pdsprj`

## Complete-project facts

Every donor has exactly these archive members: `SCRIPTS/PWRRAILS.DAT`,
`ROOT.CDB`, `ROOT.DSN`, and `PROJECT.XML`. Each CDB has four pin rows and one
property row, matching one physical four-gate package. Every ROOT.DSN object
stream starts `00 00 FF`, ends `FF FF`, has four logic subparts, 12 active
`$TERBIDIR` records, and 12 WIRE records.

| Family | ROOT.DSN object bytes | ROOT.CDB bytes | First component marker | First terminal | First WIRE |
| --- | ---: | ---: | ---: | ---: | ---: |
| 74HC00 | 3,478 | 424 | 75 | 1,555 | 1,672 |
| 74HC02 | 3,442 | 423 | 75 | 1,551 | 1,669 |
| 74HC08 | 3,426 | 423 | 75 | 1,551 | 1,668 |
| 74HC32 | 3,422 | 422 | 75 | 1,547 | 1,664 |
| 74HC86 | 3,482 | 423 | 75 | 1,551 | 1,668 |
| 74HC266 | 3,510 | 425 | 75 | 1,563 | 1,680 |

The required project-frame pattern is therefore the locked-mega-compatible
one: complete component packet(s) first, followed by active terminal/WIRE
attachment units, then `FF FF`. This is not the rejected side-terminal or
label-only path.

## Pin model and attachment evidence

Each package exposes 12 visible signal pins: four outputs and eight inputs.
The donor terminal labels encode the pin and signal role (`Pin1I1`, `Pin3O1`,
and so on); terminal orientation is `1800` on the left/input side and `0` on
the right/output side. The actual donor WIREs have two or three points and
connect the grid-snapped terminal contact to the exact package pin. Their
pin-relative coordinate and component-link-offset facts are already stored in
the component catalogue for all six families.

`74HC266` contains a user-label typo: its second `Pin5` input terminal is
package pin `6` / `I4`. The catalogue must preserve the normalized pin identity
as `6` while retaining the donor as the primary byte/geometry source.

## Emission boundary

The next 1x pack must be generated from the locked
`new_components_5x_mega.pdsprj` component placer output, not by returning any
of these donor files. The existing shared catalogue terminal placer is the only
emitter permitted. Before handoff, compare the generated package stream with
its no-terminal control and this donor set for: CDB/package count, component
prefix, component-before-attachment order, 12 terminal/WIRE units per family,
grid contact, left/right angle, link fields, and final `FF FF`.

## 74HC00 / 74HC02 locked-mega reference-width defect â€” 2026-07-13

The 74HC00 no-terminal component-placer control was cold-opened twice in local
Proteus and opened normally. It uses the required locked mega packet `U476`
(`U476:A` through `U476:D`) and must remain unchanged. The corresponding
terminalized candidate exited with code 1 before a schematic window appeared.
This is therefore not a component-placement, grid, CDB, terminal-template, or
wire-coordinate failure.

Complete comparison against the authoritative 74HC00 donor explains the
failure. The accepted donor has package reference `U53`, while the locked-mega
selection has `U476`. The component-link offsets previously stored only as
offsets from the *end of the full four-gate package*. That moved every link by
the total four-byte package-width difference. The pin-link fields actually
belong to individual subpart records, so their correct movement is one byte
for `:A`, two for `:B`, three for `:C`, and four for `:D`. The old calculation
patched fields such as HC00 pin 3 at object offset 386 instead of 383; it
overwrote the following `FF 06 U476:B` record marker and corrupted the object
stream.

The authoritative donor proves the correct link-slot frame. For 74HC00, the
relative slot offsets from each subpart end are: `A` pins 1/2/3 = -13/-9/-5,
`B` pins 4/5/6 = -13/-9/-5, `C` pins 10/9/8 = -13/-9/-5, and `D` pins
13/12/11 = -12/-8/-4. 74HC02 has the same type of package-reference-width
change (`U58` donor versus `U198` locked-mega packet) and needs the same
subpart-relative resolution, with its donor-derived pin mapping recorded in
the catalogue. The other four DIL14 families currently retain matching-width
references and are frozen until this additive branch passes their regressions.

One packet-tail qualification is essential. The locked-mega bare packet keeps
one trailing byte after the final `:D` link fields; the shared splice removes
that byte before attachments are appended. Therefore the `:D` links retain the
already-correct whole-packet end-relative offsets. Only `:A`, `:B`, and `:C`
have the catalogue-gated subpart-end offsets. Applying a direct `:D`
subpart-end offset would consume the final trailer byte and is rejected by the
link-rebase audit.

The safe repair is catalogue-gated: only profiles with explicit
`component_link_subpart_end_offsets` may resolve a link from the end of the
matching current `:A`/`:B`/`:C`/`:D` record. All profiles without that evidence
continue using the established whole-packet link offset route. The terminal
contact rule remains unchanged: terminal symbol/contact coordinates are snapped
to the 254,000 Proteus grid and each donor-derived nonzero WIRE runs from that
contact to the exact, potentially off-grid component pin.

## 74HC266 gate-B pin correction â€” 2026-07-13

The accepted 74HC266 donor contains two gate-B input terminals whose visible
labels are both headed `Pin5`: `Pin5I3` is the actual package pin 5/link slot
763, and `Pin5I4` is the actual package pin 6/link slot 767. The former
catalogue incorrectly assigned pin 6 to an invented slot 775, which crosses
the following `U77:C` record marker. That was not active donor evidence and
would corrupt the generated stream. The catalogue now uses the actual donor
slots and WIREs: pin 5 is `I3` at slot 763, pin 6 is normalized to `I4` at
slot 767. The emitted testing label is `Pin6I4`; the donor spelling remains
recorded as the source evidence. This correction is isolated to 74HC266 and
does not alter another accepted family.

## Independent A/B/C/D coordinate-frame defect â€” 2026-07-13

Proteus loaded the repaired HC02 1x file, but the visual result showed long,
crossing terminal WIREs from terminals far above the independent gate symbols.
This is a geometry-planner defect, not a loader defect. The current catalogue
stored each pin relative to the final package (`:D`) marker and the planner
used that final marker for every pin. The beautifier deliberately rearranges
the four logical subparts independently, so a package-wide translation is not
valid after placement.

The complete donor marker audit gives the safe frame: each of the four
`74HCxx` marker anchors is in object-record order `A`, `B`, `C`, `D`, and each
pin belongs to exactly one of those subparts. For example, HC02 donor anchors
relative to its `:D` anchor are `A=(-3,556,000,+2,540,000)`,
`B=(-3,556,000,0)`, `C=(0,+2,540,000)`, and `D=(0,0)`. The placer output moves
those four anchors independently. The catalogue must therefore state both the
pin-to-subpart mapping and the donor subpart-anchor delta. The planner must
calculate each pin and donor WIRE/contact from that *current subpart* anchor,
then snap only the terminal contact to the 254,000 grid. It must not use the
final package anchor as a proxy for A/B/C/D.

## Wide-reference link-frame and finalizer audit — 2026-07-13

The authoritative `74HC08_user_terminalized_july04.pdsprj` was cold-opened,
saved on a copy, and cold-opened again. Proteus kept all 12 `$TERBIDIR`
records and all 12 WIRE records. Its only `ROOT.DSN` changes were five project
metadata bytes; its `ROOT.CDB` was byte-identical. This establishes that the
donor's component-first, terminal/WIRE-tail stream is persistent, not merely
a loader-only visual result.

The shared 1x HC08 candidate was tested the same way. It also kept its 12
terminals and 12 WIREs, proving the base U66 route works, but Proteus removed
one extra explicit final `FF` on save. The donor's final WIRE coordinate itself
ends in `FF`, followed by one structural `FF`; the generated route wrote two
structural `FF` bytes. All DIL14 profiles therefore require the donor-proven
`single_ff` finalizer rather than the catalogue default `double_ff`.

The scale failure is a separate, fully explained reference-width issue. A
locked-mega HC08 package with four-character references (`U350:A` through
`U350:D`) is four bytes longer than the U66 donor package. Whole-packet-end
offsets therefore land too late in the first three records: `:A` link slots
are three bytes late, `:B` two bytes late, and `:C` one byte late. The final
`:D` slots remain correct because they are measured from the final packet end.
For HC08, donor-derived current-subpart offsets are A pins 1/2/3 =
`-13/-9/-5`, B pins 4/5/6 = `-13/-9/-5`, and C pins 9/10/8 =
`-13/-9/-5`; D remains on its existing whole-packet offsets.

This exact pattern is shared by the other quad-gate DIL14 donors and is
catalogued per pin, not inferred at runtime:

| Family | A/B/C per-subpart pin-link slots | D handling |
| --- | --- | --- |
| 74HC08 | `-13/-9/-5` in physical pin order | existing whole-packet offsets |
| 74HC32 | `-13/-9/-5` in physical pin order | existing whole-packet offsets |
| 74HC86 | `-13/-9/-5` in physical pin order | existing whole-packet offsets |
| 74HC266 | `-13/-9/-5` in its donor pin order (including pin 6/I4) | existing whole-packet offsets |

The user Save As copy of a 9-package control that terminalized only U350
removed all 12 attachments. That is expected from the mispatched A/B/C link
fields and is the acceptance check for the catalogue-only repair: the repaired
wide-reference project must retain its terminal/WIRE units after Ctrl+S and
cold reopen. No accepted two-pin, BJT, or previously accepted DIL14 U66 route
is changed.
