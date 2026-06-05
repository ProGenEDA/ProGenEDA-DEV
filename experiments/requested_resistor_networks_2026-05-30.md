# Requested Resistor Networks, 2026-05-30

## Purpose

The user rejected the previous broad acceptance set because some circuits were already used during development and might not prove generality. This batch creates the exact 15 named resistor network classes the user requested.

## Main Generator Output

Generated in:

```text
D:/Coding/protuesgen/experiments/requested_resistor_networks_2026_05_30
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

## Cases

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

## Static Results

```text
15/15 generated
15/15 contain PROJECT.XML, ROOT.DSN, ROOT.CDB, SCRIPTS/PWRRAILS.DAT
0 static validation issues
pytest: 24 passed, 40 subtests passed
```

## Superseded Visual Limitation

The generator still emits horizontal V9 resistor records. Topology is represented by repeated terminal labels, not exact drawn geometry. Proteus GUI validation is pending user screenshots/errors.

This limitation was addressed in the follow-up oriented batch after the Proteus resistor angle field was identified.

## Oriented Follow-Up Batch

Generated in:

```text
D:/Coding/protuesgen/experiments/requested_resistor_networks_oriented_2026_05_30
```

Static results:

```text
15/15 generated
0 static validation issues
pytest: 26 passed, 40 subtests passed
```

The oriented batch emits real vertical resistor visual records (`-900` tenths angle field) for the requested circuits that naturally need vertical branches: simple loop, parallel/current-divider legs, voltage-divider stacks, star arms, Wheatstone/H-bridge branches, and R-2R ladder shunts.
