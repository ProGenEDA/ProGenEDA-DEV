# Sequential Counter Donor Learning - 2026-06-09

This note covers the first two sequential/counter-only donor batches. It does
not change the locked combinational IC route.

## Scope

Current families:

- `74HC90` user input maps to the observed Proteus device marker `7490`.
- `74HC160`
- `74HC161`
- `74HC163`
- `74HC192`
- `74HC193`
- `4017`
- `4020`
- `74HC4024`

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

## V2 Manual Result And V3 Retry

User manual Proteus result for V2:

```text
T06_MIXED_74HC192_74HC193_UPDOWN_CHAIN     failed, Proteus crashed before open
T07_MIXED_4017_4020_74HC4024_DIVIDER_CHAIN failed, Proteus crashed before open
T08_MIXED_74HC161_74HC192_4017_4020_CHAIN  failed, Proteus crashed before open
```

The single-family V2 controls were not changed. The crash boundary is the
heterogeneous mixed-family assembly path, which spliced unit records out of
4-package donors and generated a combined mixed CDB/device section.

V3 retry script:

```text
python tools/proteus_generation/2026-06-09/generate_ic_sequential_counters_v3_mixed_retry_temp.py
```

V3 output:

```text
experiments/ic_sequential_counters_v3_mixed_retry_temp_2026_06_09
experiments/IC_SEQUENTIAL_COUNTERS_V3_MIXED_RETRY_TEMP_2026_06_09.zip
```

V3 changes only the mixed sequential-counter experiment:

- the final generated IC package is always sourced from donor slot 4, preserving
  donor-native final-object record shape;
- T00 is a same-family 74HC193 unit-slice control;
- T01 is a two-family 4017/4020 final-slot control;
- T06, T07, and T08 are direct retries of the failed V2 mixed cases.

Automated result:

```text
0 static validation issues
python -m pytest tests -q => 95 passed, 78 subtests passed
```

Manual Proteus testing is still pending for V3. Do not promote heterogeneous
mixed sequential-counter generation until these V3 retry files open and simulate
where applicable.

User manual Proteus result for V3:

```text
T00_CONTROL_74HC193_2X_UNIT_SLICES_FINAL_SLOT                 failed
T01_CONTROL_4017_4020_2FAMILY_FINAL_SLOT                      failed
T06_RETRY_74HC192_74HC193_UPDOWN_CHAIN_FINAL_SLOT             failed
T07_RETRY_4017_4020_74HC4024_DIVIDER_CHAIN_FINAL_SLOT         failed
T08_RETRY_74HC161_74HC192_4017_4020_CHAIN_FINAL_SLOT          failed
```

Since the same-family `T00` unit-slice control failed, the working conclusion is
that sequential-counter unit slicing is unsafe. Do not use it for this IC class.

## V4 Whole-Donor Retry

V4 avoids unit slicing completely. It starts from complete 2x/4x donor object
chunks that Proteus already accepts, then mutates only labels and same-length
device identities in-place.

Script:

```text
python tools/proteus_generation/2026-06-09/generate_ic_sequential_counters_v4_whole_donor_retry_temp.py
```

Output:

```text
experiments/ic_sequential_counters_v4_whole_donor_retry_temp_2026_06_09
experiments/IC_SEQUENTIAL_COUNTERS_V4_WHOLE_DONOR_RETRY_TEMP_2026_06_09.zip
```

V4 case list:

- `T00_CONTROL_74HC193_2X_WHOLE_DONOR_LABELS`
- `T01_RETRY_74HC192_74HC193_WHOLE_DONOR`
- `T02_RETRY_4017_4020_WHOLE_DONOR`
- `T03_RETRY_74HC161_74HC192_74HC193_74HC163_WHOLE_DONOR`
- `T04_CONTROL_4020_4X_WHOLE_DONOR_LABELS`

V4 intentionally does not force `74HC4024` into mixed 4017/4020 chains because
the 74HC4024 donor has a different visible-terminal count and longer device
marker. A manual mixed donor is required before promoting that shape.

Automated result:

```text
0 static validation issues
python -m pytest tests -q => 97 passed, 78 subtests passed
```

Manual Proteus testing is pending for V4.

## V2 Additional Pin Facts

`74HC192` visible pins:

```text
Q0 PIN3
Q1 PIN2
Q2 PIN6
Q3 PIN7
TCU PIN12
TCD PIN13
D0 PIN15
D1 PIN1
D2 PIN10
D3 PIN9
UP PIN9
DN PIN4
PL PIN11
MR PIN14
```

The `74HC192` donor labels both `D3` and `UP` as `PIN9`. V2 records pin 9 as
ambiguous and keeps signal-name aliases (`D3`, `UP`) authoritative until a
corrected donor confirms the pin number.

`74HC193` visible pins:

```text
Q0 PIN3
Q1 PIN2
Q2 PIN6
Q3 PIN7
TCD PIN13
TCU PIN12
D0 PIN15
D1 PIN1
D2 PIN10
D3 PIN9
UP PIN5
DN PIN4
PL PIN11
MR PIN14
```

`4017` visible pins:

```text
Q0 PIN3
Q1 PIN2
Q2 PIN4
Q3 PIN7
Q4 PIN10
Q5 PIN1
Q6 PIN5
Q7 PIN6
Q8 PIN9
Q9 PIN11
CO PIN12
CLK PIN14
E PIN13
MR PIN15
```

`4020` visible pins:

```text
Q0 PIN9
Q3 PIN7
Q4 PIN5
Q5 PIN4
Q6 PIN6
Q7 PIN13
Q8 PIN12
Q9 PIN14
Q10 PIN15
Q11 PIN1
Q12 PIN2
Q13 PIN3
CLK PIN10
MR PIN11
```

`74HC4024` visible pins:

```text
Q1 PIN12
Q2 PIN11
Q3 PIN9
Q4 PIN6
Q5 PIN5
Q6 PIN4
Q7 PIN3
CLK PIN1
MR PIN2
```

## Generated V2 Pack

Script:

```text
python tools/proteus_generation/2026-06-09/generate_ic_sequential_counters_v2_temp.py
```

Output:

```text
experiments/ic_sequential_counters_v2_temp_2026_06_09
experiments/IC_SEQUENTIAL_COUNTERS_V2_TEMP_2026_06_09.zip
```

The pack contains 57 cases:

- the same six donor-learning controls for each of nine families;
- three mixed-family cascade experiments:
  - `74HC192 -> 74HC193`
  - `4017 -> 4020 -> 74HC4024`
  - `74HC161 -> 74HC192 -> 4017 -> 4020`

Static result:

```text
0 static validation issues
python -m pytest tests -q => 93 passed, 78 subtests passed
```

Manual Proteus testing is still pending.
