# 74HC157 donor preflight - 2026-07-13

Scope: additive catalogue work for `74HC157` only. The shared terminal
placer and every previously accepted family remain frozen.

## Authoritative source and container

The authoritative user-terminalized source is:

`proteus_ic/donors/terminalized_catalogue_evidence/dil16_mux/74HC157/74HC157_terminalized_primary.pdsprj`

Archive members are `SCRIPTS/PWRRAILS.DAT` (17 bytes), `ROOT.CDB` (347),
`ROOT.DSN` (69,276), and `PROJECT.XML` (249). Per the user's DSN-only
instruction, `ROOT.CDB` is not decoded or changed; it is preserved unchanged
by this terminal route. Its source SHA-256 is
`09852825f3d1e8915588467c5e1b14654c6b9b048e7386f787b29fc5eb7e3ab2`.

`ROOT.DSN` SHA-256 is
`8471f954068c94c8582cb1840fa2d86e473d5f0ca29657f08688ee68912058ec`.
Its object chunk starts at absolute byte 65,707, is 2,672 bytes long, and
ends in a single structural `FF`.

## Full DSN attachment grammar

The chunk contains fourteen `$TERBIDIR` records, then one `74HC157` component
packet with its fourteen native WIRE records. This is a terminal-leading
grammar:

`chunk prefix -> 14 terminals -> separator -> component packet -> 14 WIREs -> FF`

The terminal record order is:

`4, 7, 9, 12, 2, 3, 5, 6, 11, 10, 14, 13, 1, 15`.

The component begins at chunk offset 1,535. Its clean component packet ends
at relative offset 436; the first WIRE record begins there and its `WIRE`
marker is at offset 460 (the marker is 24 bytes into its 50-byte record). The active component-link table is fourteen adjacent
four-byte fields at relative offsets 372 through 424, each ending in trailer
`01 00`. Their pin order is the same as the WIRE order:

`2, 4, 3, 5, 7, 6, 11, 9, 10, 14, 12, 13, 1, 15`.

Therefore the donor-proven clean-packet link offsets are respectively:

`-64, -60, -56, -52, -48, -44, -40, -36, -32, -28, -24, -20, -16, -12`.

For every native WIRE, its active suffix equals
`(object_chunk_absolute_start + WIRE_marker_offset - 24) & 0xffff` and the
same suffix appears both in the corresponding terminal and component-link
field. No other donor link field is unexplained.

## Pin geometry and terminal rules

The component marker anchor is `(-8,128,000, 7,874,000)`. The left pin x is
anchor x minus 508,000; the right pin x is anchor x plus 2,032,000. The
donor uses `1800` for every left pin and `0` for every right pin.

| Pin order | Terminal label | Side | Physical pin / donor contact |
| --- | --- | --- | --- |
| 2 | `1A PIN 2` | left | `(-8,636,000, 7,620,000)` |
| 4 | `1Y PIN 4` | right | `(-6,096,000, 7,620,000)` |
| 3 | `1B PIN 3` | left | `(-8,636,000, 7,366,000)` |
| 5 | `2A PIN 5` | left | `(-8,636,000, 7,112,000)` |
| 7 | `2Y PIN 7` | right | `(-6,096,000, 7,112,000)` |
| 6 | `2B PIN 6` | left | `(-8,636,000, 6,858,000)` |
| 11 | `3A PIN 11` | left | `(-8,636,000, 6,604,000)` |
| 9 | `3Y PIN 9` | right | `(-6,096,000, 6,604,000)` |
| 10 | `3B PIN 10` | left | `(-8,636,000, 6,350,000)` |
| 14 | `4A PIN 14` | left | `(-8,636,000, 6,096,000)` |
| 12 | `4Y PIN 12` | right | `(-6,096,000, 6,096,000)` |
| 13 | `4B PIN 13` | left | `(-8,636,000, 5,842,000)` |
| 1 | `NA/B PIN 1` | left | `(-8,636,000, 5,334,000)` |
| 15 | `E PIN 15` | left | `(-8,636,000, 5,080,000)` |

The donor WIREs are native zero-length records at the physical pin/contact.
They establish the packet/link grammar but are not a sufficient production
attachment by themselves: the current accepted rule requires an on-grid
terminal contact plus a nonzero short WIRE to the exact pin. The shared
catalogue planner must therefore retain the donor terminal-leading record
order and link slots while emitting its existing nonzero grid-contact route.

## Generated-tail correction from the rejected 1x loader gate

The first locked-mega 1x candidate preserved the donor grammar but used the
ordinary `single_ff` finalizer. Its last transformed WIRE endpoint has a
little-endian coordinate tail ending in byte `FF` (`... 00 8c ba ff`). The
ordinary normalizer treated that coordinate byte as an already-present object
finalizer and emitted no structural terminator. The captured local Proteus
gate showed `Fatal Error: Internal Exception: access violation in module
'VGDVC.DLL' [000190DA]` before any schematic could load. This is not a Bad
Object Record and must not be Ctrl+S-saved.

The authoritative donor ends its final coordinate in `00` followed by one
structural `FF`; it establishes that this grammar needs exactly one final
structural byte. The correct existing shared policy is therefore
`append_explicit_single_ff`: append one byte after the generated WIRE payload
without inspecting the payload's final coordinate byte. This is a 74HC157-only
catalogue fact. It does not alter the shared emitter or any frozen family.

## Planned additive profile facts

The profile must be upgraded from its old geometry cache to cite this donor,
declare the terminal-leading order, the single-`FF` finalizer, the fourteen
link offsets/trailers, the donor labels, and a nonzero grid-contact-to-pin WIRE
policy. The locked mega's fresh bare packet has now been compared with the
436-byte donor component packet: its U33 reference is one byte longer than
the donor's U1 reference, so its live component payload is 437 bytes long.
The reserved link slots retain the same end-relative offsets. The underlying
437-byte component payload changes only at the fourteen four-byte link fields.

## Rejected candidate: stale component-placer finalizer byte

The first two generated candidates were rejected by the local loader with the
same `VGDVC.DLL` access violation. This is not a Bad Object Record, so neither
candidate was saved or treated as Proteus-recovered evidence. The explicit
single-`FF` tail repair was necessary but insufficient.

The complete three-way DSN comparison then found the remaining structural
difference. The selected locked-mega `RawComponentGroup` has 438 bytes and
ends in a source finalizer byte `00`; normal component placement emits only its
first 437 bytes and replaces that finalizer with the stream `FF`. The
terminal-leading route incorrectly reinserted all 438 raw bytes before its
native WIRE records. Consequently the generated first WIRE marker was 1 byte
late at chunk offset 1,997. The authoritative donor marker is 1,995; allowing
for U33's one additional reference byte, the required generated marker is
1,996. Every active component-link field was likewise one byte late (1,909
through 1,961 rather than 1,908 through 1,960).

All other inspected differences are intentional and donor-accounted: U33 is
one byte longer than U1, component and terminal coordinates are translated,
terminal contacts are grid-aligned, WIREs are nonzero and end at exact pins,
and suffixes are rebased from the final WIRE addresses. Terminal record order,
labels, orientations, WIRE header/template bytes, fourteen link trailers, and
terminal-leading packet order match the donor. `ROOT.CDB` remains untouched as
requested.

The only justified next mutation is therefore an additive HC157 catalogue flag
that tells the shared terminal placer to remove the component-placer's raw
finalizer byte before patching the terminal-leading component payload. That
will restore the donor-relative packet width and link positions without
touching any accepted family, coordinate rule, WIRE encoding, or CDB member.

## Corrected 1x result

With that HC157-only flag, the locked-mega U33 candidate has a 437-byte live
component payload, the first WIRE marker is 1,996 (the donor's 1,995 plus the
one-byte U33 reference delta), and the component-link slots are at 1,908
through 1,960. The output contains fourteen grid-aligned terminal contacts,
fourteen nonzero short WIREs to exact pins, and all terminal/component suffix
links are rebased from final ROOT.DSN WIRE addresses.

The focused HC157/HC151/HC76/4027 test selection passed (7 tests) and
`compileall` passed. The final 1x project cold-opened visibly after the
12-second stability interval with no dialog, then cold-opened a second time
without a dialog. Both screenshots show the U33 74HC157 and all fourteen
terminals. Since these were normal opens rather than Bad Object Record
recoveries, no Ctrl+S was issued; the disposable copy SHA-256 remained
`D97AB3CF99A9B1C558C54D488AFCE24AE71B207984D4BC7A78EC5A139134C64C`.

Scale validation and user visual acceptance remain pending. Frozen families
were not regenerated or changed.

## 9x and 15x scale result

Fresh locked-mega placements were generated through the unchanged shared
profile. The 9x file has 126 terminals and 126 nonzero WIREs; the 15x file has
210 of each. Independent DSN checks verify unique terminal suffixes, matching
WIRE-address suffix sets, exactly one terminal and one component `01 00` link
field per WIRE suffix, and grid-aligned terminal contacts for every attachment
unit. All 9 or 15 components respectively report the profile-gated raw
finalizer trim.

Both files cold-opened visibly after the 12-second stability wait and then
cold-reopened normally. No Bad Object Record appeared, so neither copy was
saved. The 9x copy hash stayed
`EA9C7BE79915850FAA0F4AF7F733BE5075876D588287D2712DA0872A035B0F7F`; the
15x copy hash stayed
`401911BA553C415EEC0BA484478F0721FDAA4CA26221FAE0EAB45296734183AD`.
User visual acceptance remains pending; frozen families were not changed.
