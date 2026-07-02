# Terminal Placer CAP Attachment V2

## Purpose

This focused pack runs the accepted component placer and beautifier before the
shared `component_terminal_placer.py` dispatcher. It processes `1x`, `3x`, and
`15x` CAP cases only.

## Binary Evidence

- Family handler: `CAP/v2`
- Manual evidence: `cap2_with_terminals_manual plus the user-accepted mixed_passive.convert_production_terminals route`
- Terminals: left `$TERBIDIR` at 180 degrees; right at 0 degrees
- CAP geometry: pins at body `+/-508000`; terminal symbols another `254000`
  outward; one zero-length donor-native wire record at each true pin
- CAP object order: all right bidirectional records first, followed by repeated
  left bidirectional/component/left-wire/right-wire groups
- Non-final right wires: 49 bytes; final right wire: 50 bytes ending in `FF`
- Suffixes: donor-native `0x0238` progression
- Input JSON: reused from the accepted family beautifier experiment; only the
  requested count and donor path are changed

## Test Order

Open the non-`_BASE` project in each case folder. Confirm every component has
one attached bidirectional terminal on each side and each terminal touches the
real capacitor pin. The zero-length attachment records may not render as a
visible wire segment. Run netlist/simulation and report any bad-object, DLL,
duplicate-reference, or floating-terminal error.

Static validation passed locally. Proteus acceptance remains pending.

## Static Verification

- Focused and cumulative component-placer suite: `42 passed`
- Object-stream cursor reconstruction: exact for 1x, 3x, and 15x
- Terminal/component suffix matches: passed
- Zero-length attachment coordinates at every CAP pin: passed
- Right-wire sizes: 49 bytes for non-final groups, 50 bytes for final group
- Compile checks: passed
