# Terminal Placer CAP-ELEC Attachment V3

## Purpose

This focused pack runs the accepted component placer and beautifier before the
shared `component_terminal_placer.py` dispatcher. It processes `1x`, `3x`, and
`15x` CAP-ELEC cases only.

## Binary Evidence

- Family handler: `CAP-ELEC/v3`
- Manual evidence: `user-accepted analog_misc_batch1 8ELEC-CAP donor and its donor-native bidirectional label-mutation controls`
- Terminals: left `$TERBIDIR` at 180 degrees; right at 0 degrees
- CAP-ELEC geometry: pins at body `+/-508000`; terminal symbols another
  `254000` outward; one zero-length donor-native wire record at each true pin
- CAP-ELEC object order: repeated right bidirectional/left bidirectional/
  component/left-wire/right-wire groups
- Suffixes: donor-native `0x02A8` progression from `0x0120`/`0x0152`
- Donor blank terminal labels are replaced with compact non-empty labels, as in
  the user-accepted analog/misc label-mutation controls
- Non-final right wires: 49 bytes; final right wire: 50 bytes ending in `FF`
- Input JSON: reused from the accepted family beautifier experiment; only the
  requested count and donor path are changed

## Test Order

Open the non-`_BASE` project in each case folder. Confirm every component has one attached bidirectional terminal on each side and each terminal touches the real component pin. The
zero-length attachment records may not render as a visible wire segment. Run
netlist/simulation and report any bad-object, DLL, duplicate-reference, or
floating-terminal error. The tested component family is electrolytic capacitor.

Static validation passed locally. Proteus acceptance remains pending.

## Static Verification

- Focused and cumulative component-placer suite: `49 passed`
- Object-stream cursor reconstruction: exact for 1x, 3x, and 15x
- Terminal/component suffix matches: passed
- Zero-length attachment coordinates at every CAP-ELEC pin: passed
- Right-wire sizes: 49 bytes for non-final groups, 50 bytes for final group
- Compile checks: passed
