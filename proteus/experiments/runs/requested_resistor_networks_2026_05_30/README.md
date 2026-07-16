# Requested Resistor Networks, 2026-05-30

This batch was generated from the current general V9 resistor JSON generator in response to the user's 15 named circuit list.

Each case folder contains:

```text
input.json
<case>.pdsprj
<case>.ROOT.CDB.bin
<case>.ROOT.DSN.bin
manifest.json
README_TEST_FIRST.txt
generator_version.txt
```
Static result:

```text
15/15 generated
15/15 contain PROJECT.XML, ROOT.DSN, ROOT.CDB, SCRIPTS/PWRRAILS.DAT
0 static validation issues
pytest: 24 passed, 40 subtests passed
```

Proteus GUI validation is pending user screenshots/errors.

Test order:

```text
01_SIMPLE_LOOP
02_SERIES_CIRCUIT
03_PARALLEL_CIRCUIT
04_SERIES_PARALLEL_COMBO
05_BASIC_VOLTAGE_DIVIDER
06_MULTI_STEP_VOLTAGE_DIVIDER
07_CURRENT_DIVIDER
08_DELTA_NETWORK
09_STAR_Y_NETWORK
10_DELTA_TO_STAR_SETUP
11_WHEATSTONE_BRIDGE
12_BALANCED_WHEATSTONE_BRIDGE
13_UNBALANCED_WHEATSTONE_BRIDGE
14_H_BRIDGE_RESISTOR_VERSION
15_R_2R_LADDER_NETWORK
```
