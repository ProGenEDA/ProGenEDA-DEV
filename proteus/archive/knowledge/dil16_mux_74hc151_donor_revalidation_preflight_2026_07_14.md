# 74HC151 donor revalidation preflight — 2026-07-14

## Authority and scope

The sole terminal-attachment authority is the user-provided project
`proteus_ic/donors/terminalized_catalogue_evidence/dil16_mux/74HC151/74HC151_user_terminalized_july04.pdsprj`.
The sole component-placement donor remains
`proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`.
This revalidation must use the existing unified
`src/proteusgen/component_terminal_placer.py`; it does not introduce a
family-specific emitter or a second workflow.

## Complete donor container audit

The project contains exactly `SCRIPTS/PWRRAILS.DAT`, `ROOT.CDB`, `ROOT.DSN`,
and `PROJECT.XML`. Their byte sizes are respectively 17, 343, 109816, and
249 bytes. `ROOT.CDB` SHA-256 is
`35a715253bd68ca47336ac915ade4098135c22c61ab23c5cbf694b6ab9e15515`; it is
read and preserved rather than inferred.

`ROOT.DSN` SHA-256 is
`4393ff7677fa78293dd4648e13bbd770ff059ca9b0017ba15439e2a0ada77393`. Its
object stream begins at absolute offset 106232 and is 2687 bytes long
(`382efc4f889cbf3fe8fafab3ef13add458fd3767a66e048d69306f89be71a4ed`). The
complete stream has one 74HC151 component packet followed by fourteen native
terminal/WIRE attachment units and its structural finalizer.

## Attachment contract derived from the actual donor

The unit order is pin `5`, `6`, `4`, `3`, `2`, `1`, `15`, `14`, `13`, `12`,
`11`, `10`, `9`, `7`, with labels `Pin5Y`, `Pin6NY`, `Pin4X0`, `Pin3X1`,
`Pin2X2`, `Pin1X3`, `Pin15X4`, `Pin14X5`, `Pin13X6`, `Pin12X7`, `Pin11A`,
`Pin10B`, `Pin9C`, and `Pin7E`.

All fourteen terminal contacts are on the 254000-unit Proteus grid. The two
right pins have 0-degree terminal orientation; every left pin has 180-degree
orientation. The fourteen WIRE marker offsets are 569, 726, 883, 1040, 1205,
1362, 1520, 1686, 1844, 2010, 2175, 2340, 2496, and 2660. Every WIRE is
nonzero; six are three-point donor polylines, so their bends must be retained.
Terminal suffixes and WIRE suffixes match exactly in donor order:
41241, 41398, 41555, 41712, 41877, 42034, 42192, 42358, 42516, 42682, 42847,
43012, 43168, and 43332. The final bytes contain a coordinate byte of `FF`
followed by the separate structural finalizer; the profile's explicit
single-finalizer policy is therefore required.

## Revalidation plan

No plausible unaccounted-for donor difference remains before emitting a new
candidate. Regenerate only a locked-mega 1x control and its complete shared
catalogue route, compare every packet/terminal/WIRE/link fact against this
donor, and run the local Proteus cold-open/cold-reopen gate. If it passes,
generate 9x and 15x using the existing contact-retarget policy, run the same
gate, and capture the 15x canvas. No completed two-pin, DIL8, 74HC76, or 4027
 route may be changed during this work.

## Fresh result

The current shared route was regenerated from the locked mega without any
terminal-placer source modification. The 1x output has the donor's 2687-byte
object stream width, labels, orientations, 14 WIRE marker offsets, all WIRE
polylines, and finalizer. Its only 56 byte differences from the authoritative
donor are the expected fourteen terminal and fourteen component active-link
suffixes allocated from final ROOT.DSN WIRE addresses. Its `ROOT.CDB` is
byte-identical to the no-terminal locked-mega control.

The native-contact and grid-contact diagnostic stages, the complete active
stage, and the active cold reopen all reached a normal Proteus schematic
window after the 12-second settled wait, without a Bad Object Record, fatal,
LXLCORE, or library dialog. The normal copies were not Ctrl+S-saved and their
hashes stayed unchanged.

The complete active 9x and 15x projects contain respectively 126 and 210
grid-aligned, nonzero terminal/WIRE attachment units. In both projects the
terminal suffix set is unique and equals the final WIRE suffix set. Both scale
projects and their cold reopens reached normal Proteus windows unchanged. The
15x capture visibly shows repeatedly terminalized 74HC151 symbols. These are
loader/persistence results; user visual acceptance remains the layout
authority.
