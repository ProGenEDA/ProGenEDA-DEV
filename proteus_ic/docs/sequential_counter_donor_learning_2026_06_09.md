# Sequential Counter Donor Learning - 2026-06-09

This note covers the first sequential/counter-only donor batch. It does not
change the locked combinational IC route.

## Scope

Current families:

- `74HC90` user input maps to the observed Proteus device marker `7490`.
- `74HC160`
- `74HC161`
- `74HC163`

Skipped for now:

- `NE555`
- remaining counter/divider ICs not yet supplied as donors
- all combinational ICs

## Terminal Policy

For this sequential IC experiment, every visible counter pin uses donor-native
`$TERBIDIR` terminals.

This is intentionally different from the locked combinational IC route, where
IC signal pins remain `$TERINPUT` / `$TEROUTPUT`.

Rationale:

- Counter/divider pin direction is more stateful and pin-sensitive.
- The supplied donors already attach `$TERBIDIR` to every visible signal pin.
- Same-name bidirectional terminals are the least risky first route for
  sequential/control-pin learning.

## Learned Pin Facts

`74HC90`/`7490` visible pins:

```text
CKA PIN14
CKB PIN1
R0(1) PIN2
R0(2) PIN3
R9(1) PIN6
R9(2) PIN7
Q0 PIN12
Q1 PIN9
Q2 PIN8
Q3 PIN11
```

`74HC160`, `74HC161`, and `74HC163` visible pins:

```text
MR PIN1
CLK PIN2
D0 PIN3
D1 PIN4
D2 PIN5
D3 PIN6
ENP PIN7
LOAD PIN9
ENT PIN10
Q3 PIN11
Q2 PIN12
Q1 PIN13
Q0 PIN14
RCO PIN15
```

Important: pin 14 is not hidden supply for these counters. It is a visible
signal pin (`CKA` on `7490`, `Q0` on `74HC160/161/163`).

## Generated V1 Pack

Script:

```text
python tools/proteus_generation/2026-06-09/generate_ic_sequential_counters_v1_temp.py
```

Output:

```text
experiments/ic_sequential_counters_v1_temp_2026_06_09
experiments/IC_SEQUENTIAL_COUNTERS_V1_TEMP_2026_06_09.zip
```

The pack contains 24 cases:

- exact donor repack
- single-device E001 transplant
- single-device label mutation
- two-device unique labels
- four-device chain labels
- four-device chain labels with preserved R/C/L donor material

Static result:

```text
0 static validation issues
python -m pytest tests -q => 90 passed, 78 subtests passed
```

Manual Proteus testing is still pending.
