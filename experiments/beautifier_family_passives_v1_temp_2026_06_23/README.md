# Beautifier Family Passives V1

Generated on 2026-06-23.

This pack starts the new family-by-family beautifier workflow. It tests only passive-family coordinate movement in the shared component placer/beautifier pipeline.

## Code Under Test

- `src/proteusgen/component_beautifier.py`
- `src/proteusgen/component_placer.py` via `generate_component_placement_project`

## New Coordinate Policy Under Test

The beautifier now uses explicit coordinate-offset plans for:

- `RESISTOR`
- `CAP`
- `REALIND`
- `CAP-ELEC`
- `DIODE`

Other families still use the previous generic coordinate scanner until their family-specific plans are learned.

## Test Files

- `P01_RESISTOR_5X_FAMILY_PLAN/P01_RESISTOR_5X_FAMILY_PLAN.pdsprj`: Five resistors should be visible, separated on the beautifier grid, with names/values staying near their symbols.
- `P02_CAP_5X_FAMILY_PLAN/P02_CAP_5X_FAMILY_PLAN.pdsprj`: Five capacitors should be visible, separated on the beautifier grid, with labels/values attached and no overlap.
- `P03_REALIND_5X_FAMILY_PLAN/P03_REALIND_5X_FAMILY_PLAN.pdsprj`: Five inductors should be visible, separated on the beautifier grid, with labels/values attached and no overlap.
- `P04_CAP_ELEC_5X_FAMILY_PLAN/P04_CAP_ELEC_5X_FAMILY_PLAN.pdsprj`: Five electrolytic capacitors should be visible and separated. This specifically checks that the old false coordinate near 16,384,000 is no longer moved as part of the packet.
- `P05_DIODE_5X_FAMILY_PLAN/P05_DIODE_5X_FAMILY_PLAN.pdsprj`: Five diodes should be visible, separated on the beautifier grid, with labels attached and no overlap.
- `P06_PASSIVE_MIXED_3X_EACH_FAMILY_PLAN/P06_PASSIVE_MIXED_3X_EACH_FAMILY_PLAN.pdsprj`: Mixed passive pack. All 15 components should be visible on the grid with no strange far-away labels, overlaps, or bad object records.

## User Results

Pending.

## Next Step

After user confirmation, update each case README and either lock this passive-family coordinate method or record the failing family-specific offset.
