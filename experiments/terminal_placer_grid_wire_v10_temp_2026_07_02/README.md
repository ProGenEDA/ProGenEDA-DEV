# Terminal Placer Grid-Wire V10

All cases are placed from the unchanged mega donor:

`proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`

SHA-256: `1222561d29622193d4eaa34aa830a341dee47abe376d1b971390dd6baad7958c`

The donor contains the broad component set including FUSE and POT-HG. It is
only the component-placer test input. Terminal placement does not inspect the
donor path or packet origin.

V10 keeps each beautified component at its exact coordinates. For every
researched two-pin family, it snaps the terminal contact to the nearest
Proteus `254000 x 254000` grid intersection and emits a short WIRE from that
grid contact to the exact component pin.

Test `V10_01` through `V10_06` first, then mixed `V10_07`, `V10_08`, and
`V10_09`. Check that:

1. no Bad Object Record appears;
2. terminals render on grid intersections;
3. a visible short wire reaches every exact component pin;
4. unsupported controls remain unchanged and terminal-free;
5. Ctrl+S/reopen preserves the result.

The active attachment profiles in this checkpoint are RESISTOR, CAP,
CAP-ELEC, REALIND, VSOURCE, and CSOURCE. Other two-pin families in this same
donor remain preserved controls until their pin-link fields and pin geometry
are separately proved; V10 does not guess binary offsets.
