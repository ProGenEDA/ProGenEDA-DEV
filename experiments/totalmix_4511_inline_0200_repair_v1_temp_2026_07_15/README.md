# All-49 mixed terminal repair: inline 4511 / `0200`

This pack is a fresh generation from the locked
`new_components_5x_mega.pdsprj` donor. It does not copy the user’s manual
project at runtime.

- `ALL49_BARE_COMPONENT_PLACER_1X.pdsprj` is the component-placer and
  beautifier control with no terminal attachments.
- `ALL49_TERMINALIZED_1X_4511_INLINE_0200_REPAIR.pdsprj` is the corresponding
  shared-terminal-placer candidate.

The mixed-profile repair keeps the complete 4511 terminal block adjacent to
U9, uses its donor-proven `0200` active component-link trailer, and leaves only
74HC151 in the later mux-tail zone.

Mechanical checks passed:

- 49 placed component groups retained before and after terminal attachment;
- 318 active `$TERBIDIR` records and 318 short `WIRE` records;
- all terminal suffixes match final ROOT.DSN WIRE addresses;
- U9 has 14 active terminal/component-pin links using `0200`.

No local Proteus process was launched, saved, or closed for this pack. It still
needs the user’s Proteus visual/open acceptance.
