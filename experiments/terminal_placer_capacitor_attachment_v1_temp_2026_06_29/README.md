# Terminal Placer Capacitor Attachment V1

## Purpose

This is the second family-specific terminal-attachment test. It uses the
accepted component placer and beautifier, then the shared terminal placer with
the new `CAP/v1` handler. The JSON comes from the accepted capacitor
beautifier probe and only the count is changed for C01, C03, and C15.

## Why This Is Focused

Older capacitor work proved that ordinary input/output terminal ordering is
fragile when multiple terminal-attached capacitors are synthesized. This V1
pack is narrower:

- bare `CAP` packets come from the current main mega donor;
- bidirectional terminals come from the production terminal templates;
- capacitor pin-link suffix fields are patched from byte-proven CAP offsets;
- donor-proven body-center geometry determines the real left/right pin points;
- short wires are emitted explicitly so attachment is visible and testable.

## V1 Capacitor Structure

For each capacitor V1 emits:

- one left `$TERBIDIR` at 180 degrees;
- one right `$TERBIDIR` at 0 degrees;
- terminal symbols one fixed bidirectional-terminal span away from each pin;
- one short wire from each terminal contact to its real pin;
- capacitor link suffixes patched into the bare mega packet tail.

The binary object order follows the same accepted shared pattern:

```text
header
left terminal records
right terminal records
separator
capacitor + left short wire + right short wire
...
final FF
```

## Test Cases

- C01: one capacitor, two attached terminals.
- C03: three capacitors, six attached terminals.
- C15: fifteen capacitors, thirty attached terminals.

Each case folder contains the reused `payload.json`, bare base project,
terminalized project, placer manifest, terminal plan, and `WHAT_TO_CHECK.txt`.

## Acceptance

For every case:

1. Open the terminalized file, not the `_BASE` file.
2. Confirm every capacitor has one bidirectional terminal on each side.
3. Confirm left arrows face into the body from the left and right arrows from the right.
4. Confirm each terminal reaches its capacitor pin through a visible short wire.
5. Confirm no terminal floats, overlaps, or lands between the plates instead of on a pin.
6. Run simulation/netlist and report any DLL, bad-object, duplicate-reference,
   or unconnected-pin error.

## Result

Static generation passed on 2026-06-29:

- C01/C03/C15 have exactly two terminals and two short wires per capacitor;
- terminal suffixes are patched into the capacitor tail fields;
- local regression tests pass with the shared terminal dispatcher;
- Proteus acceptance is still pending user testing.
