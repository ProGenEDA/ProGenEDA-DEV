# Three-pin BJT 1x solo V34

Test only the four `_sa` files under `01_test_these_bjt_sa`:

1. `T001_NPN_1x_sa`
2. `T002_PNP_1x_sa`
3. `T003_2N3904_1x_sa`
4. `T004_2N4401_1x_sa`

Matching no-terminal component-placer controls are under
`00_no_terminal_controls`. Each case was generated from the locked mega donor,
beautified, and then passed through the one shared
`src/proteusgen/component_terminal_placer.py` implementation.

V34 changes only the failed BJT branch. The user-accepted V33 1x routes for
`NMOSFET`, `2N7000`, and `BS170` remain locked and were not regenerated.

The accepted NPN/PNP donor evidence proves that these BJT WIRE records exist as
active records but are zero-length exactly at the grid-aligned component pins.
V34 therefore removes V33's extra outward grid step for BJT pins. It also
preserves donor terminal-record order:

- NPN-derived: `COLLECTOR`, `EMITTER`, `BASE`.
- PNP: `BASE`, `COLLECTOR`, `EMITTER`.

Static checks passed for all four cases: one placed component, three active
terminals, three active zero-length WIRE units, terminal contact equal to exact
pin, final-address link rebasing valid, and one final `FF`. Proteus open/render
acceptance is still required before generating 9x/15x/23x.
