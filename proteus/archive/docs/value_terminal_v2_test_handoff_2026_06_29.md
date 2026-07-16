# Value and Terminal V2 Test Handoff

## Why V2 Exists

Proteus feedback showed that V1 CAP-ELEC mutation failed and V1 bidirectional
terminals were not attached. V2 narrows the value syntax and expands terminal
coverage without pretending that visual proximity is wiring.

## Value Pack

Archive:

`experiments/VALUE_CHANGER_PROBE_V2_SAFE_VALUES_TEMP_2026_06_26.zip`

Check:

1. Every project opens.
2. Every project displays 15 components.
3. Values visibly vary across the row.
4. `V03_CAP_ELEC_15X_VALUES` opens without bad-object or DLL errors and shows
   values such as `1uF`, `2uF`, and `3uF`.

The source cases use explicit unit-bearing values (`1V`..`9V`, `1A`..`9A`).
VSINE and VPULSE mutation remain blocked.

## Terminal Pack

Archive:

`experiments/TERMINAL_PLACER_BIDIR_PROBE_V2_ALL_FAMILIES_TEMP_2026_06_26.zip`

Cases:

- T01: passives and discrete devices.
- T02: all 22 currently supported IC families plus both displays.
- T03: sources, controls, and new-component families.

Check:

1. Each project opens without a DLL/bad-object error.
2. Left-side bidirectional triangles face into the component from the left.
3. Right-side bidirectional triangles face into the component from the right.
4. Report which families have terminals directly touching real pins.
5. Report which families show gaps, wrong Y anchors, or need short wires.

Expected limitation: V2 emits no `WIRE` records. It is a pin-anchor diagnostic,
not the final attached-terminal implementation.
