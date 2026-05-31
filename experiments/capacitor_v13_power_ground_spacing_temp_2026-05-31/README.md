# Capacitor V13 Power/Ground Spacing Diagnostics 2026-05-31

## Status

Temporary, pending Proteus test. Supersedes V12 for the next user check.

## Trigger

User requested more horizontal and vertical component distance, then asked to generate the 15 capacitor circuits with power terminal and ground.

## Method

V13 keeps the user-accepted V10/V11 manual capacitor object order:

```text
all capacitor output terminals first
then repeated $TERINPUT / CAPACITOR / left WIRE / right WIRE groups
non-final right WIRE records are 49 bytes
final right WIRE record is 50 bytes and ends FF
```

It adds the locked resistor power/ground endpoint method:

```text
one donor-derived $TERPOWER -> $TEROUTPUT(V0) bridge
powered capacitor endpoints stay ordinary $TERINPUT(V0)
G0 right endpoints become $TERGROUND(G0)
```

Spacing changed from V12's `2540000` grid to `3810000` internal units on both x and y axes.

## Generated Local Pack

```text
D:/Coding/protuesgen/experiments/capacitor_v13_power_ground_spacing_temp_2026_05_31
```

ZIP:

```text
D:/Coding/protuesgen/experiments/CAPACITOR_V13_POWER_GROUND_SPACING_TEMP_2026_05_31.zip
sha256: 2ecf1bbda47de0f21ede6d8730acb0607fa688d94ed3cc2fab0c801e1fae9818
```

Generator script:

```text
D:/Coding/protuesgen/tools/proteus_generation/2026-05-31/generate_capacitor_v13_power_ground_spacing_temp.py
```

## Static Results

```text
pytest: 31 passed
tests/test_results.py after knowledge update: 2 passed
static_validation_issues: empty for all 15 cases
project count: 15 .pdsprj files
total capacitor count: 65
```

## Test Order

```text
01. 01_SIMPLE_LOOP/01_SIMPLE_LOOP.pdsprj
02. 02_SERIES_CIRCUIT/02_SERIES_CIRCUIT.pdsprj
03. 03_PARALLEL_CIRCUIT/03_PARALLEL_CIRCUIT.pdsprj
04. 04_SERIES_PARALLEL_COMBO/04_SERIES_PARALLEL_COMBO.pdsprj
05. 05_BASIC_VOLTAGE_DIVIDER/05_BASIC_VOLTAGE_DIVIDER.pdsprj
06. 06_MULTI_STEP_VOLTAGE_DIVIDER/06_MULTI_STEP_VOLTAGE_DIVIDER.pdsprj
07. 07_CURRENT_DIVIDER/07_CURRENT_DIVIDER.pdsprj
08. 08_DELTA_NETWORK/08_DELTA_NETWORK.pdsprj
09. 09_STAR_Y_NETWORK/09_STAR_Y_NETWORK.pdsprj
10. 10_DELTA_TO_STAR_SETUP/10_DELTA_TO_STAR_SETUP.pdsprj
11. 11_WHEATSTONE_BRIDGE/11_WHEATSTONE_BRIDGE.pdsprj
12. 12_BALANCED_WHEATSTONE_BRIDGE/12_BALANCED_WHEATSTONE_BRIDGE.pdsprj
13. 13_UNBALANCED_WHEATSTONE_BRIDGE/13_UNBALANCED_WHEATSTONE_BRIDGE.pdsprj
14. 14_H_BRIDGE_RESISTOR_VERSION/14_H_BRIDGE_RESISTOR_VERSION.pdsprj
15. 15_R_2R_LADDER_NETWORK/15_R_2R_LADDER_NETWORK.pdsprj
```

## What To Check

```text
Each project opens without VGDVC or loader errors.
Power terminal bridge is present for V0.
G0 endpoints show ground terminals.
Visible capacitor count matches each case manifest.
Component spacing is more comfortable than V12.
```

