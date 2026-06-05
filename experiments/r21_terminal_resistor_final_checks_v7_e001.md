# R21 Terminal + Resistor Final Checks V7, E001 Only

## User clarification

The user clarified that the terminal method should not be locked in yet:

```text
terminal coordinates are still off
terminal + resistor integration is not yet checked
current success is only empty terminal generation
```

So V7 was created as a final-check pack before locking the technique.

## Local artifact

```text
R21_TERMINAL_RESISTOR_FINAL_CHECKS_V7_E001.zip
```

## Base guarantee

All generated projects in this pack use:

```text
E001 PROJECT.XML
E001 SCRIPTS/PWRRAILS.DAT
generated ROOT.CDB
generated/rebuilt ROOT.DSN
```

No full R4 project is used as the base.

The previous R4/resistor data is used only indirectly as a record-schema donor already incorporated into the E001 resistor generator path.

## Why V7 exists

Known stable layer:

```text
E001 -> generated 21 CDB-backed resistors -> opens
```

Partially validated layer:

```text
generated terminal visible records can open in small cases
large terminal sets can open but coordinates/layout are still wrong
wire variants still produce bad-object errors
```

V7 therefore avoids explicit wire records and checks:

```text
1. one resistor baseline
2. 21 resistor baseline
3. one resistor with two terminals using three coordinate hypotheses
4. two-resistor series with terminals
5. full requested R21 topology using terminals placed at resistor pin-contact positions
```

## Coordinate hypotheses tested

### OLD_SPACING

Uses the earlier terminal spacing inherited from the donor layout:

```text
input symbol x  = resistor_x - 508000
output symbol x = resistor_x + 1778000
```

This is expected to leave a visible gap without wires.

### CONTACT_TIP

Uses the inferred terminal contact-point offset:

```text
input contact point  = symbol_x + 254000
output contact point = symbol_x - 254000
```

So for direct contact with resistor pins:

```text
input symbol x  = left_pin - 254000
output symbol x = right_pin + 254000
```

This is the likely final method if terminals need to touch pins without explicit wire objects.

### SYMBOL_ON_PIN

Places terminal symbol coordinates directly on the resistor pin coordinates:

```text
input symbol x  = left_pin
output symbol x = right_pin
```

This is included as a visual/coordinate sanity check.

## Files generated

```text
CONTROL_E001_EMPTY_BASE.pdsprj
TEST_V7_R1_RESISTOR_ONLY_E001_BASELINE.pdsprj
TEST_V7_R21_RESISTORS_ONLY_E001_BASELINE.pdsprj
TEST_V7_R1_TERMINALS_OLD_SPACING_NO_WIRES.pdsprj
TEST_V7_R1_TERMINALS_CONTACT_TIP_NO_WIRES.pdsprj
TEST_V7_R1_TERMINALS_SYMBOL_ON_PIN_NO_WIRES.pdsprj
TEST_V7_R2_SERIES_TERMINALS_CONTACT_TIP_NO_WIRES.pdsprj
TEST_V7_R2_SERIES_TERMINALS_CONTACT_TIP_INTERLEAVED_NO_WIRES.pdsprj
TEST_V7_R21_FINAL_CONTACT_TIP_TERMS_FIRST_NO_WIRES_SAFE_VALUES.pdsprj
TEST_V7_R21_FINAL_CONTACT_TIP_INTERLEAVED_NO_WIRES_SAFE_VALUES.pdsprj
TEST_V7_R21_EXPERIMENTAL_TRUE_VISIBLE_VALUES_CONTACT_TIP_NO_WIRES.pdsprj
```

## Test order

```text
1. CONTROL_E001_EMPTY_BASE.pdsprj
2. TEST_V7_R1_RESISTOR_ONLY_E001_BASELINE.pdsprj
3. TEST_V7_R21_RESISTORS_ONLY_E001_BASELINE.pdsprj
4. TEST_V7_R1_TERMINALS_OLD_SPACING_NO_WIRES.pdsprj
5. TEST_V7_R1_TERMINALS_CONTACT_TIP_NO_WIRES.pdsprj
6. TEST_V7_R1_TERMINALS_SYMBOL_ON_PIN_NO_WIRES.pdsprj
7. TEST_V7_R2_SERIES_TERMINALS_CONTACT_TIP_NO_WIRES.pdsprj
8. TEST_V7_R2_SERIES_TERMINALS_CONTACT_TIP_INTERLEAVED_NO_WIRES.pdsprj
9. TEST_V7_R21_FINAL_CONTACT_TIP_TERMS_FIRST_NO_WIRES_SAFE_VALUES.pdsprj
10. TEST_V7_R21_FINAL_CONTACT_TIP_INTERLEAVED_NO_WIRES_SAFE_VALUES.pdsprj
11. Optional: TEST_V7_R21_EXPERIMENTAL_TRUE_VISIBLE_VALUES_CONTACT_TIP_NO_WIRES.pdsprj
```

## Values

All generated files store real values in ROOT.CDB:

```text
R1 = 1k
R2 = 2k
...
R9 = 9k
RA = 10k
RB = 11k
...
RL = 21k
```

Safe visible value labels remain fixed width:

```text
1k, 2k, ..., 9k, Ak, Bk, ..., Lk
```

An optional experimental file tests true visible values `10k..21k` by using variable-length value fields.

## Requested R21 topology

The final R21 files implement:

```text
R1..R7    first 7-resistor series branch
R8..RE    second 7-resistor series branch in parallel with R1..R7
RF..RL    final 7-resistor series branch after the parallel block
```

Node labels:

```text
N0 - R1 - A1 - R2 - A2 - R3 - A3 - R4 - A4 - R5 - A5 - R6 - A6 - R7 - M0
N0 - R8 - B1 - R9 - B2 - RA - B3 - RB - B4 - RC - B5 - RD - B6 - RE - M0
M0 - RF - C1 - RG - C2 - RH - C3 - RI - C4 - RJ - C5 - RK - C6 - RL - Z0
```

## What success means

If the R1 terminal coordinate checks open:

```text
terminal record structure is still valid when placed against resistor geometry
```

If R2 series opens and netlisting/simulation starts:

```text
terminal labels and resistor endpoint placement are likely sufficient for simple resistor networks
```

If the final R21 contact-tip file opens and simulates:

```text
we can lock in resistor + terminal no-wire generation as the first usable resistor-network generator method
```

If visual placement is correct but simulation topology is wrong:

```text
explicit wire records or a different terminal contact offset will still be needed
```

If bad object returns:

```text
the issue is object ordering or terminal count scaling, not resistor CDB generation
```
