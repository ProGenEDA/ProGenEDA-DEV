# Mixed selective terminal placer V1

This pack exercises the actual reusable pipeline:

`input.json -> component placer -> binary beautifier -> shared terminal placer`

The accepted terminal allowlist is:

- RESISTOR/v3
- CAP/v2
- CAP-ELEC/v3
- REALIND/v2
- VSOURCE/v4
- CSOURCE/v4

DIODE, NPN, and 74HC08 are deliberate negative controls. Their complete
beautified component packets must remain byte-identical and must receive no
terminal or short-wire records.

## Proteus checks

Open the non-`_BASE` project in each case.

1. T01: one of every accepted family plus one of each negative control.
2. T02: three of every accepted family plus repeated negative controls.
3. T03: negative controls only. Its final project is byte-identical to `_BASE`.

For T01/T02, verify that each accepted two-pin component has exactly two
attached bidirectional terminals. Verify that DIODE, NPN, and all four units of
each 74HC08 package remain terminal-free. Report open, render, and simulation
results separately because static validation is not Proteus acceptance.
