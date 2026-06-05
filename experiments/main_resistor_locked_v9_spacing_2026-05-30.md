# Main Resistor Locked V9 Spacing, 2026-05-30

## Purpose

After checking the locked-method generated projects, the user accepted the method and requested one visual adjustment: vertically stacked component/terminal groups need more spacing, while each terminal should stay at the same or closer distance from its own component.

## Change

The main generator increased safe vertical row spacing:

```text
old y spacing: 1524000 internal units
new y spacing: 2540000 internal units
terminal-to-component offsets: unchanged
power/ground method: unchanged
```

Auto-placement and dense manual-position stretching now use the same safe grid:

```text
x spacing = 2540000
y spacing = 2540000
```

## Output

Generated in the active repo:

```text
D:/Coding/protuesgen/experiments/main_resistor_locked_v9_spacing_2026_05_30/REQUESTED_15_LOCKED_SPACING
```

Case 06 `MULTI_STEP_VOLTAGE_DIVIDER` now uses resistor y positions:

```text
5080000, 2540000, 0, -2540000, -5080000
```

## Static Results

```text
15/15 generated
0 static validation issues
pytest: 31 passed, 40 subtests passed
OBJECT DATA audit: passed
```

The audit confirmed the locked V9 method stayed unchanged:

```text
exactly one $TERPOWER per generated project
all resistor left endpoints are $TERINPUT
ground endpoints are $TERGROUND right endpoints
visual_wire_count = 0 for all projects
```
