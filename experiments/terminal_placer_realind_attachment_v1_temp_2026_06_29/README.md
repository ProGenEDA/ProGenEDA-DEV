# Terminal Placer REALIND Attachment V1

## Purpose

This focused pack runs the accepted component placer and beautifier before the
shared `component_terminal_placer.py` dispatcher. It processes `1x`, `3x`, and
`15x` REALIND cases only.

## Binary Evidence

- Family handler: `REALIND/v1`
- Manual evidence: `inductor_01_single_free + inductor_02_two_terminal`
- Terminals: left `$TERBIDIR` at 180 degrees; right at 0 degrees
- Attachment: one active component link and one short wire per pin
- Input JSON: reused from the accepted family beautifier experiment; only the
  requested count and donor path are changed

## Test Order

Open the non-`_BASE` project in each case folder. Confirm every component has
one attached bidirectional terminal on each side, with a short green wire
meeting the real pin. Then run netlist/simulation and report any bad-object,
DLL, duplicate-reference, or floating-terminal error.

Static validation passed locally. Proteus acceptance remains pending.
