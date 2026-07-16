# All-49 compact visibility repair

The earlier all-49 candidate retained all records but placed late families as
far as `+595,944,960` vertical schematic units. Proteus did not visibly render
the gates, 4511, and 74HC151 in the user’s inspection.

This pack keeps the same shared `totalmix_combined_v1` terminal route but asks
the component placer/beautifier for a compact, interleaved mixed layout:

- `compact_family_flow: true`
- `mixed_family_interleave: true`
- `terminal_grid_alignment: true`
- `shelf_width: 152,400,000`

The wide candidate spans `-6,370,320…138,938,000` horizontally and
`-5,201,920…53,360,320` vertically, comparable to the accepted user donor’s
visible coordinate range.

- `ALL49_BARE_COMPONENT_PLACER_WIDE_1X.pdsprj` is the no-terminal control.
- `ALL49_TERMINALIZED_WIDE_1X_4511_INLINE_0200.pdsprj` is the candidate.

Static checks: 49 retained component groups, 318 terminals, 318 WIRE records,
grid-aligned contacts, nonzero short WIRE paths, and final-address terminal
links. A visible Proteus launch of a disposable copy reached Schematic Capture
without an error dialog. User visual acceptance is pending.
