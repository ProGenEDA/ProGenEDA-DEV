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

At generation time, no local Proteus process was launched, saved, or closed.
The following gate records the subsequent explicit user-authorized check.

## Local Proteus gate — 2026-07-15

After the user explicitly authorized Proteus process control, a disposable copy
of the terminalized candidate was cold-launched twice. Both launches reached
the Schematic Capture window, remained stable for the required additional
12-second delay, and exposed no `Bad Object Record`, `Fatal Error`, `LXLCORE`,
or device-library dialog. The second launch left the copied project hash
unchanged, so no Ctrl+S repair was needed. The copy was then opened visibly for
the user's visual inspection and deliberately left open.
