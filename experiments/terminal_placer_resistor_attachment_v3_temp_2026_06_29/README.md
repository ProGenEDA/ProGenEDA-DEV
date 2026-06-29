# Terminal Placer Resistor Attachment V3

## Purpose

This is the first family-specific terminal-attachment test. It uses the
accepted component placer and beautifier, then the unified terminal placer.
The JSON comes from the accepted resistor beautifier probe and only the count
is changed for R01, R03, and R15.

## Previous Result

- Value changer V2: user-confirmed working.
- Generic terminal placer V2: rejected because terminals were incorrectly
  positioned and not electrically attached.

V2 used bounding-box edges and no wires. V3 does not use that method.

## V3 Resistor Structure

For each horizontal resistor V3 emits:

- one left `$TERBIDIR` at 180 degrees;
- one right `$TERBIDIR` at 0 degrees;
- terminal symbols at the locked 508,000-unit resistor spacing;
- one donor-derived 254,000-unit short wire on each side;
- resistor pin-link suffixes matching the corresponding terminal suffixes.

The binary object order follows the locked resistor route:

```text
header
left terminal records
right terminal records
separator
resistor + left short wire + right short wire
...
final FF
```

## Test Cases

- R01: one resistor, two attached terminals.
- R03: three resistors, six attached terminals.
- R15: fifteen resistors, thirty attached terminals.

Each case folder contains the reused `payload.json`, bare base project,
terminalized project, placer manifest, terminal plan, and `WHAT_TO_CHECK.txt`.

## Acceptance

For every case:

1. Open the terminalized file, not the `_BASE` file.
2. Confirm every resistor has one terminal on each side.
3. Confirm left arrows face right and right arrows face left toward the body.
4. Confirm there is a short green wire from each terminal contact to its pin.
5. Confirm no terminal floats or overlaps the resistor.
6. Run simulation/netlist and report any DLL, bad-object, duplicate-reference,
   or unconnected-pin error.

## Result

Static generation passed on 2026-06-29:

- R01/R03/R15 have exactly two terminals and two short wires per resistor;
- terminal suffixes match resistor pin-link fields;
- short-wire endpoints match terminal contacts and resistor pins;
- object lengths and final terminators are exact;
- the component-placer test file passes.

Proteus acceptance remains pending user testing.
