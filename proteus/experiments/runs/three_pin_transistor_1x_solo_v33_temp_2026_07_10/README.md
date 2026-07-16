# Three-pin transistor 1x solo V33

This is a focused Proteus acceptance pack. It contains only one component per
case. There are no scaled or mixed outputs.

Test the seven files under `01_terminalized_solo_sa` in this order:

1. `T001_NPN_1x_sa`
2. `T002_PNP_1x_sa`
3. `T003_NMOSFET_1x_sa`
4. `T004_2N3904_1x_sa`
5. `T005_2N4401_1x_sa`
6. `T006_2N7000_1x_sa`
7. `T007_BS170_1x_sa`

Matching component-placer-only controls are under `00_no_terminal_controls`.
Each case includes its input `request.json`; each terminalized case also has a
`terminal_report.json`.

All components were selected from the locked mega donor by the shared component
placer, beautified, and then terminalized only by
`src/proteusgen/component_terminal_placer.py`. Terminalized donor projects were
used only as byte/geometry evidence.

Static result: 7/7 component placements valid, 7/7 terminal reports valid,
exactly one selected component and three terminals/WIREs per output, all grid
and contact checks valid, and all final terminal/component link checks valid.
These checks are not Proteus acceptance; record the open/render result for each
file before enabling scale or mixed generation.

Structural evidence used in V33:

- NPN/PNP and their BJT aliases: terminal-leading, component, then WIREs, with
  one final `FF`.
- NMOSFET and its MOSFET aliases: component-first terminal/WIRE units, complete
  donor-shaped drain/source doglegs, and final `FF FF`.
