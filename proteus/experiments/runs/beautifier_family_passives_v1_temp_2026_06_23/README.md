# Beautifier Family Passives V1

Generated on 2026-06-23.

This pack starts the new family-by-family beautifier workflow. It tests only passive-family coordinate movement in the shared component placer/beautifier pipeline.

## Code Under Test

- `src/proteusgen/component_beautifier.py`
- `src/proteusgen/component_placer.py` via `generate_component_placement_project`

## Coordinate Policy That Was Tested

The V1 beautifier used explicit fixed coordinate-offset plans for:

- `RESISTOR`
- `CAP`
- `REALIND`
- `CAP-ELEC`
- `DIODE`

This fixed-offset policy is now rejected. User Proteus testing reported every
case in this pack failed with `LXLCORE.dll`.

Follow-up byte inspection showed those fixed offsets touched small
font/body constants such as `3276800`, `381000`, `203200`, and `254000`, not
the real mega-donor coordinate fields.

## Test Files

- `P01_RESISTOR_5X_FAMILY_PLAN/P01_RESISTOR_5X_FAMILY_PLAN.pdsprj`: Five resistors should be visible, separated on the beautifier grid, with names/values staying near their symbols.
- `P02_CAP_5X_FAMILY_PLAN/P02_CAP_5X_FAMILY_PLAN.pdsprj`: Five capacitors should be visible, separated on the beautifier grid, with labels/values attached and no overlap.
- `P03_REALIND_5X_FAMILY_PLAN/P03_REALIND_5X_FAMILY_PLAN.pdsprj`: Five inductors should be visible, separated on the beautifier grid, with labels/values attached and no overlap.
- `P04_CAP_ELEC_5X_FAMILY_PLAN/P04_CAP_ELEC_5X_FAMILY_PLAN.pdsprj`: Five electrolytic capacitors should be visible and separated. This specifically checks that the old false coordinate near 16,384,000 is no longer moved as part of the packet.
- `P05_DIODE_5X_FAMILY_PLAN/P05_DIODE_5X_FAMILY_PLAN.pdsprj`: Five diodes should be visible, separated on the beautifier grid, with labels attached and no overlap.
- `P06_PASSIVE_MIXED_3X_EACH_FAMILY_PLAN/P06_PASSIVE_MIXED_3X_EACH_FAMILY_PLAN.pdsprj`: Mixed passive pack. All 15 components should be visible on the grid with no strange far-away labels, overlaps, or bad object records.

## User Results

Failed. User reported all six files gave `LXLCORE.dll`.

## Codex Observation

The fixed passive-family offset table is unsafe and must not be reused. For the
first `RESISTOR` packet in the main mega donor, real coordinate fields are
length-prefixed text/body-marker coordinates:

- `4/8`: reference text `R1`
- `73/77`: value text `10k`
- `150/154`: model/name text `RESISTOR`
- `236/240`: property text `{PRIMITIVE=ANALOGUE}`
- `313/317`: symbol body marker `RESISTOR`

Equivalent parsed fields were found for `CAP`, `REALIND`, `CAP-ELEC`, and
`DIODE`. The next experiment must use parsed coordinate fields only and start
with resistor-only probes before widening back to other passive families.

## Next Step

Generate a narrow resistor-only parsed-coordinate probe using the real
`generate_component_placement_project` path. Do not regenerate this V1 archive
as if it were pending; it is a rejected experiment.
