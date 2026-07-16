# Capacitor V12 Requested 15 Network Diagnostics 2026-05-31

## Status

Superseded by V13 before Proteus test. Use V13 for the next check because it adds wider spacing plus real power/ground terminal records.

## Trigger

User reported the V11 6C and 21C capacitor networks work, then requested the same 15 resistor-network acceptance circuits generated with capacitors.

## Method

V12 uses the accepted V10/V11 manual-donor record shape:

```text
all $TEROUTPUT records first
then repeated $TERINPUT / CAPACITOR / left WIRE / right WIRE groups
non-final right WIRE records are 49 bytes
final right WIRE record is 50 bytes and ends FF
```

The pack is generated from E001. It uses terminal-label topology and ordinary two-character labels `V0` and `G0`; it does not introduce power/ground terminal symbols or standalone bus/junction wire records.

## Generated Local Pack

```text
D:/Coding/protuesgen/experiments/capacitor_v12_requested15_temp_2026_05_31
```

ZIP:

```text
D:/Coding/protuesgen/experiments/CAPACITOR_V12_REQUESTED15_TEMP_2026_05_31.zip
sha256: a7f37e0fc2507525176fd3046e57da21168fc44c357eed9c9cc781a69e2a4f3f
```

Generator script:

```text
D:/Coding/protuesgen/tools/proteus_generation/2026-05-31/generate_capacitor_v12_requested15_temp.py
```

## Static Results

```text
pytest: 31 passed
tests/test_results.py after knowledge update: 2 passed
static_validation_issues: empty for all 15 cases
project count: 15 .pdsprj files
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
The visible capacitor count matches the case manifest.
The terminal-label topology matches the named circuit.
Values and refs render as C1.. with uF values.
```
