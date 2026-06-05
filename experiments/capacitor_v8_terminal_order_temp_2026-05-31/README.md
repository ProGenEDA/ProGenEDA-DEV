# Capacitor V8 Terminal Order Diagnostics 2026-05-31

## Status

Temporary, pending Proteus test.

## Trigger

User reported V7 results:

```text
worked: T01, T02, T03, T05
failed: T04, T06
opened but visually wrong: T07
```

T07 screenshot showed only a partial two-terminal-cap circuit: C1 appeared, but
the second capacitor group did not render as a complete C2 with N3/N4 terminals.

## Hypothesis

Multiple terminal-attached capacitors may need the locked resistor V9 ordering:

```text
object header 00
all input terminals
all output terminals
separator 00
component + short-wire groups
single final FF at the end
```

V7 T07 used terminals-first ordering, but it did not include the V9 separator
byte and did not fully render the second capacitor.

## Generated Local Pack

```text
D:/Coding/protuesgen/experiments/capacitor_v8_terminal_order_temp_2026_05_31
```

ZIP:

```text
D:/Coding/protuesgen/experiments/CAPACITOR_V8_TERMINAL_ORDER_TEMP_2026_05_31.zip
sha256: d54a09ab869c6c322b947b0be72141194522a773d8a5a5cf894f0cdb132b877e
size_bytes: 171575
```

Generator script:

```text
D:/Coding/protuesgen/tools/proteus_generation/2026-05-31/generate_capacitor_v8_terminal_order_temp.py
```

## Static Results

```text
fixture registry: valid=true
pytest: 31 passed, 40 subtests passed
static_validation_issues: empty for all 6 cases
```

## Test Order

Open in order. T01 should reproduce a case already reported working. For T02-T06,
report whether the file opens and whether it shows two complete capacitors with
N1/N2 and N3/N4 terminals.

```text
1. CAP_V8_T01_V7_T05_REPRO_FREE_FIRST_TERMINAL_LAST/CAP_V8_T01_V7_T05_REPRO_FREE_FIRST_TERMINAL_LAST.pdsprj
2. CAP_V8_T02_TWO_TERMINAL_RES_SUFFIX_V9_ORDER_ZERO_FLAGS/CAP_V8_T02_TWO_TERMINAL_RES_SUFFIX_V9_ORDER_ZERO_FLAGS.pdsprj
3. CAP_V8_T03_TWO_TERMINAL_RES_SUFFIX_V9_ORDER_DONOR_FLAG/CAP_V8_T03_TWO_TERMINAL_RES_SUFFIX_V9_ORDER_DONOR_FLAG.pdsprj
4. CAP_V8_T04_TWO_TERMINAL_CAP_SUFFIX_V9_ORDER_ZERO_FLAGS/CAP_V8_T04_TWO_TERMINAL_CAP_SUFFIX_V9_ORDER_ZERO_FLAGS.pdsprj
5. CAP_V8_T05_TWO_TERMINAL_CAP_SUFFIX_V9_ORDER_DONOR_FLAG/CAP_V8_T05_TWO_TERMINAL_CAP_SUFFIX_V9_ORDER_DONOR_FLAG.pdsprj
6. CAP_V8_T06_TWO_TERMINAL_RES_SUFFIX_V9_ORDER_VERTICAL_STAGGER/CAP_V8_T06_TWO_TERMINAL_RES_SUFFIX_V9_ORDER_VERTICAL_STAGGER.pdsprj
```

## Decision Rule

If T02 displays two capacitors correctly, V9 ordering plus zero CDB flags is the
candidate terminal-capacitor method.

If T02 fails but T03 works, the C2 `FFFFFFFF` component-table flag matters for
terminal-attached capacitor records.

If T02/T03 fail but T04/T05 work, CAP_T02 suffix spacing is required.

If T06 works while T02 is visually wrong, placement/staggering is required even
with V9 ordering.
