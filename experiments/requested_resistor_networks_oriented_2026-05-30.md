# Requested Resistor Networks Oriented, 2026-05-30

Status: **superseded**.

This batch proved the resistor rotation field, but it is not the current production method. It emitted direct power endpoint markers and standalone visual wires. The current locked method is recorded in `experiments/main_resistor_locked_v9_method_2026-05-30.md`.

## Purpose

The user correctly objected that the first 15 requested resistor-network batch still emitted horizontal resistor symbols, so bridge/star/ladder layouts were not visually representative.

This follow-up batch verifies a generator update that writes real Proteus resistor rotation fields, generates vertical endpoint stubs, and appends optional standalone visible wires for buses and bridge/junction links.

## Evidence Used

Public Proteus sample projects contain resistor visual records where the four bytes after final model placement `x/y` encode rotation:

```text
00 00 00 00 = horizontal
7c fc 00 00 = -900 tenths of a degree, vertical down
```

Wire endpoint records in the same samples confirm that a vertical-down resistor uses first pin `(x, y)` and second pin `(x, y - 1270000)`.

## Main Generator Output

Generated in:

```text
D:/Coding/protuesgen/experiments/requested_resistor_networks_oriented_2026_05_30
```

Every case has:

```text
input.json
<case>.pdsprj
<case>.ROOT.CDB.bin
<case>.ROOT.DSN.bin
manifest.json
README_TEST_FIRST.txt
generator_version.txt
```

## Static Results

```text
15/15 generated
0 static validation issues
pytest: 27 passed, 40 subtests passed
```

Angle scan over generated outputs:

```text
01_SIMPLE_LOOP                         [-900]
02_SERIES_CIRCUIT                      [0, 0, 0, 0]
03_PARALLEL_CIRCUIT                    [-900, -900, -900, -900]
04_SERIES_PARALLEL_COMBO               [0, -900, -900, -900]
05_BASIC_VOLTAGE_DIVIDER               [-900, -900]
06_MULTI_STEP_VOLTAGE_DIVIDER          [-900, -900, -900, -900, -900]
07_CURRENT_DIVIDER                     [-900, -900, -900, -900, -900]
08_DELTA_NETWORK                       [0, -900, 0]
09_STAR_Y_NETWORK                      [-900, -900, 0]
10_DELTA_TO_STAR_SETUP                 [0, -900, 0, -900, -900, 0]
11_WHEATSTONE_BRIDGE                   [-900, -900, -900, -900]
12_BALANCED_WHEATSTONE_BRIDGE          [-900, -900, -900, -900, 0]
13_UNBALANCED_WHEATSTONE_BRIDGE        [-900, -900, -900, -900, 0]
14_H_BRIDGE_RESISTOR_VERSION           [-900, -900, -900, -900, 0]
15_R_2R_LADDER_NETWORK                 [0, 0, 0, 0, -900, -900, -900, -900, -900]
```

Standalone visual-wire counts:

```text
01_SIMPLE_LOOP                         0
02_SERIES_CIRCUIT                      0
03_PARALLEL_CIRCUIT                    2
04_SERIES_PARALLEL_COMBO               2
05_BASIC_VOLTAGE_DIVIDER               0
06_MULTI_STEP_VOLTAGE_DIVIDER          0
07_CURRENT_DIVIDER                     2
08_DELTA_NETWORK                       1
09_STAR_Y_NETWORK                      0
10_DELTA_TO_STAR_SETUP                 1
11_WHEATSTONE_BRIDGE                   2
12_BALANCED_WHEATSTONE_BRIDGE          2
13_UNBALANCED_WHEATSTONE_BRIDGE        2
14_H_BRIDGE_RESISTOR_VERSION           2
15_R_2R_LADDER_NETWORK                 1
```

## Remaining Limitation

This fixes horizontal-only resistor objects for locked 90-degree vertical layouts and adds explicit visible bus/junction wires when the JSON asks for them. Arbitrary diagonal resistor symbols and a fully automatic physical router are still experimental and must not be treated as locked until a separate donor/evidence batch passes Proteus GUI open/save testing.
