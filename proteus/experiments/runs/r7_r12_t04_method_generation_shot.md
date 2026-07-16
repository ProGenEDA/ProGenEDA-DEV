# R7/R12 Generation Shot Using the T04 Method

Generated local test pack:

```text
R7_R12_T04_METHOD_GENERATION_SHOT.zip
```

## User result that motivated this

The user tested the earlier R5 pack and reported:

```text
All files opened.
T04 was best.
T04 worked with simulation.
Only problem: the 5th resistor was on top of/too close to the 4th resistor, so it was mainly a location problem.
```

The key winning approach was:

```text
T04_R5_DSN_EXTENDED_ONLY_CDB_R4_CONTROL
```

Meaning:

```text
ROOT.CDB stayed as the valid R4 control CDB.
ROOT.DSN was extended with one additional visible resistor record.
```

This is an important empirical breakthrough: at least for this isolated resistor-display case, adding a visible resistor record in ROOT.DSN can open and run even without extending ROOT.CDB beyond the R4 control state.

## What this pack tests

This pack extends the exact T04 idea to 7 and 12 visible resistors.

Files:

```text
CONTROL_R4_four_real.pdsprj
CONTROL_T04_R5_DSN_EXTENDED_ONLY_WORKED.pdsprj
TEST_R7_DOWN_PLUS_Y_T04_METHOD_DSN_ONLY_CDB_R4.pdsprj
TEST_R7_DOWN_MINUS_Y_T04_METHOD_DSN_ONLY_CDB_R4.pdsprj
TEST_R12_DOWN_PLUS_Y_T04_METHOD_DSN_ONLY_CDB_R4.pdsprj
TEST_R12_DOWN_MINUS_Y_T04_METHOD_DSN_ONLY_CDB_R4.pdsprj
README_TEST_FIRST.txt
manifest.json
```

## Generation method

Base file:

```text
CONTROL_R4_four_real.pdsprj
```

Preserved:

```text
PROJECT.XML
ROOT.CDB
SCRIPTS/PWRRAILS.DAT
```

Generated/modified:

```text
ROOT.DSN
```

DSN changes:

```text
- Extracted the existing fixed-size 346-byte visible resistor records.
- Rebuilt records R1..R7 or R1..R12.
- Patched two-character ref/value fields.
- Patched visible binding/index-like uint32 at record offset +324.
- Patched coordinate-like fields:
    +4/+8      component ID label x/y
    +72/+76    component value label x/y
    +146/+150  SUBCKT hidden label x/y
    +231/+235  PROPERTIES hidden label x/y
    +312/+316  actual component body x/y
- Ensured only the final record ends in 0xFF; all previous records end in 0x00.
- Patched pointer before first `ISIS CIRCUIT FILE`.
- Patched pointer after `__DEFAULT__\0\0`.
- Ensured byte before second `ISIS CIRCUIT FILE` is 0xFF.
```

## Naming limitation

The record has fixed two-character fields, so for 10/11/12:

```text
R10 -> RA, value Ak
R11 -> RB, value Bk
R12 -> RC, value Ck
```

This avoids variable-length string editing during this test.

## Coordinates

Two coordinate variants are included because the vertical sign direction is still not fully proven:

```text
DOWN_PLUS_Y   uses +1,270,000 per new row
DOWN_MINUS_Y  uses -1,270,000 per new row
```

Test PLUS first. If rows go the wrong way or overlap, test MINUS.

## What to report

For each generated test:

```text
opens? yes/no
visible resistor count
coordinates/rows sane? yes/no
simulation starts? yes/no
any no-model message source?
Design Explorer count if checked
```

## Interpretation

If R7/R12 open and show all requested visible resistors, the T04 method scales for isolated visible resistor placement.

If they open but simulation/model messages mention only R4 or similar, that suggests ROOT.CDB still controls simulation/model database while ROOT.DSN controls visible schematic records.

If R7 works but R12 fails, then the DSN-visible-only trick has a practical count/section/registry threshold.

If both fail, then the R5 success may have been a narrow tolerance case.
