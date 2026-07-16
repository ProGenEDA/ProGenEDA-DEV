# 4027 1x reference-width repair

This folder contains a locked-mega component-placer control and the matching
terminalized result emitted through the shared
`src/proteusgen/component_terminal_placer.py`.

- `S02_4027_1X_REFERENCE_WIDTH_NO_TERMINAL.pdsprj` is the 1x control.
- `S02_4027_1X_REFERENCE_WIDTH_DONOR_CONTACT_sa.pdsprj` has fourteen
  direct grid-contact terminals and fourteen active donor-native WIRE units.

The old candidate had a two-byte active link-prefix trim. The accepted donor
shows that one of those bytes was actually the additional character in
`U13:A/B` versus the donor's `U1:A/B` references. The
catalogue now removes only the one donor-proven zero padding byte.

Proteus loader evidence:

- visible cold open: `G09_4027_1X_REFERENCE_WIDTH_BEFORE_CLOSE.png`;
- foregrounded cold reopen: `G11_4027_1X_REFERENCE_WIDTH_COLD_REOPEN_FOREGROUND_BEFORE_CLOSE.png`.

Neither normal open was Ctrl+S-saved. The G08 recovery evidence for the
rejected prior candidate remains in the sibling
`06_local_proteus_gate` folder.
