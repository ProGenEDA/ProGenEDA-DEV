# Terminal Placer REALIND Attachment V2

## Purpose

This focused pack runs the accepted component placer and beautifier before the
shared `component_terminal_placer.py` dispatcher. It processes `1x`, `3x`, and
`15x` REALIND cases only.

## Binary Evidence

- Family handler: `REALIND/v2`
- Manual evidence: `inductor_05_six_terminal plus the user-accepted INDUCTOR_V8 sequential donor route and locked mixed_rcl bidirectional conversion`
- Terminals: left `$TERBIDIR` at 180 degrees; right at 0 degrees
- REALIND geometry: pins at body `+/-762000`; terminal symbols another
  `254000` outward; one zero-length donor-native wire record at each true pin
- REALIND object order: repeated left bidirectional/right bidirectional/
  component/left-wire/right-wire groups
- Suffixes: donor-native `0x02A8` progression from `0x01B2`/`0x01E4`
- Non-final right wires: 49 bytes; final right wire: 50 bytes ending in `FF`
- Input JSON: reused from the accepted family beautifier experiment; only the
  requested count and donor path are changed

## Test Order

Open the non-`_BASE` project in each case folder. Confirm every component has
one attached bidirectional terminal on each side and each terminal touches the
real inductor pin. The zero-length attachment records may not render as a
visible wire segment. Run netlist/simulation and report any bad-object, DLL,
duplicate-reference, or floating-terminal error.

Static validation passed locally. Proteus acceptance remains pending.

## Static Verification

- Focused and cumulative component-placer suite: `43 passed`
- Object-stream cursor reconstruction: exact for 1x, 3x, and 15x
- Terminal/component suffix matches: passed
- Zero-length attachment coordinates at every REALIND pin: passed
- Right-wire sizes: 49 bytes for non-final groups, 50 bytes for final group
- Compile checks: passed
