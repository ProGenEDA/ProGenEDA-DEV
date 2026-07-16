# Mixed IC Focused V3

## Why This Exists

`MIXED_IC_FOCUSED_V3_TEMP_2026_06_10` replaces the broad V2 layout retry with a
smaller diagnostic pack.

User testing of V2 showed:

- every case opened, and most simulated;
- all cases had visible artifacts from moved IC regions;
- T03 and T05 still failed simulation;
- removing visible `74HC4060` was the wrong direction because the real task is
  to learn how to keep it working.

The artifact cause is now identified: V2 moved the IC body and terminal symbol
coordinates, but not:

- `$TERBIDIR` terminal-label coordinates stored later in the same terminal
  record;
- component text/value/subckt/property text coordinates stored outside terminal
  records.

## Command

```powershell
python tools/proteus_generation/2026-06-10/generate_mixed_ic_focused_v3_temp.py
```

## Output

```text
experiments/mixed_ic_focused_v3_temp_2026_06_10
experiments/MIXED_IC_FOCUSED_V3_TEMP_2026_06_10.zip
```

Archive SHA-256:

```text
04dcde698d20de292989026788676b0315fc4772cef56b49cfc6b612579b6aa4
```

## Corrected Layout Rule

When translating a complete donor-derived IC region, move all of these together:

- `$TERBIDIR` terminal symbol x/y;
- `$TERBIDIR` terminal label x/y;
- `WIRE` endpoints;
- component ID/value/subckt/properties text x/y;
- IC body anchor x/y.

Do not translate only the body and pin symbols. That creates the floating text
artifacts seen in V2.

## Cases

- `T01_TEXTFIX_SHIFT_REGISTERS_WITH_DIVIDERS`
  - Text-aligned retry of the V2 T01 shape.
- `T02_TEXTFIX_DECODER_WITH_SYNC_COUNTERS`
  - Text-aligned retry of the V2 T02 shape.
- `T03_ANALOG_RCL_SHIFT_REGISTERS`
  - Accepted real mixed donor subset with RLC, NPN, PNP, LM741, CAP-ELEC,
    `74HC595`, and `74HC165`.
- `T04_ANALOG_RCL_DIVIDERS`
  - Accepted real mixed donor subset with RLC, NPN, PNP, LM741, CAP-ELEC,
    `4017`, `4020`, and `74HC4024`.
- `T05_4060_RLC_SOLO_CONTROL`
  - Accepted solo `74HC4060` donor with RLC present.
- `T06_4060_WITH_ANALOG_RCL_PREFIX`
  - Focused `74HC4060` isolation from an accepted mixed donor, keeping the
    analog/RLC prefix.
- `T07_NE555_RLC_SOLO_CONTROL`
  - Whole-donor `NE555` with RLC control for the coming timer path.

## Static Result

```text
static_issue_cases: {}
```

Targeted regression:

```powershell
python -m pytest tests/test_cdb_parser.py tests/test_mixed_ic_analog_donors.py -q
```

Result:

```text
19 passed
```

## Manual Test Focus

Test in order:

```text
T01, T02, T03, T04, T05, T06, T07
```

Use the results as follows:

- If T01/T02 still show floating labels or component text, the coordinate model
  is still incomplete.
- If T03/T04 work, keep using Proteus-authored mixed analog donors for
  RLC/NPN/PNP/LM741/CAP-ELEC integration while synthetic generation catches up.
- Compare T05 and T06 to learn whether `74HC4060` needs its solo donor metadata
  or a mixed analog/RLC bundle to simulate.
