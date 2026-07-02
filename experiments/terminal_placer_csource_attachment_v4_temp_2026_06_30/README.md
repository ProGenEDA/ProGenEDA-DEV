# Terminal Placer CSOURCE Attachment V4

## Purpose

This focused pack runs the accepted component placer and beautifier before the
shared `component_terminal_placer.py` dispatcher. It processes `1x`, `3x`, and
`15x` CSOURCE cases only.

## Binary Evidence

- Family handler: `CSOURCE/v4`
- Manual evidence: `user-accepted bidirectional DCI V3 route and the accepted V15 CSOURCE terminal/body/wire donor`
- Terminals: input role `$TERBIDIR` at 180 degrees; output role at 0 degrees
- CSOURCE pin geometry follows the accepted V15 source unit: input at body
  `(+508000,+254000)`, output at `(+508000,-1270000)`, with terminal symbols
  `254000` outward from their zero-length pin records
- CSOURCE object order: repeated input bidirectional/output bidirectional/
  component/input-wire/output-wire groups
- Suffixes: accepted source progression `0x7000`/`0x7032`, step `0x0080`
- Non-final output wires: 49 bytes; final output wire: 50 bytes ending in `FF`
- Input JSON: reused from the accepted family beautifier experiment; only the
  requested count and donor path are changed

## Test Order

Open the non-`_BASE` project in each case folder. Confirm every DC current source has an attached 180-degree input endpoint and 0-degree output endpoint at the two donor-native source pins. The
zero-length attachment records may not render as a visible wire segment. Run
netlist/simulation and report any bad-object, DLL, duplicate-reference, or
floating-terminal error. The tested component family is DC current source.

Static validation passed locally. Proteus acceptance remains pending.

## Static Verification

- Focused and cumulative component-placer suite: `49 passed`
- Object-stream cursor reconstruction: exact for 1x, 3x, and 15x
- Terminal/component suffix matches: passed
- Zero-length attachment coordinates at every CSOURCE pin: passed
- Output-wire sizes: 49 bytes for non-final groups, 50 bytes for final group
- Compile checks: passed
